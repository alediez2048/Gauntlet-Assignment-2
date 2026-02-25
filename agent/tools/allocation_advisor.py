"""Asset Allocation Advisor tool."""

from __future__ import annotations

from typing import Any, Final

from agent.clients.ghostfolio_client import GhostfolioClient, GhostfolioClientError
from agent.tools.base import ToolResult

_ASSET_CLASSES: Final[tuple[str, ...]] = (
    "EQUITY",
    "FIXED_INCOME",
    "LIQUIDITY",
    "COMMODITY",
    "REAL_ESTATE",
    "ALTERNATIVE_INVESTMENT",
)
_TARGET_ALLOCATIONS: Final[dict[str, dict[str, float]]] = {
    "conservative": {
        "EQUITY": 40.0,
        "FIXED_INCOME": 50.0,
        "LIQUIDITY": 10.0,
        "COMMODITY": 0.0,
        "REAL_ESTATE": 0.0,
        "ALTERNATIVE_INVESTMENT": 0.0,
    },
    "balanced": {
        "EQUITY": 60.0,
        "FIXED_INCOME": 30.0,
        "LIQUIDITY": 10.0,
        "COMMODITY": 0.0,
        "REAL_ESTATE": 0.0,
        "ALTERNATIVE_INVESTMENT": 0.0,
    },
    "aggressive": {
        "EQUITY": 80.0,
        "FIXED_INCOME": 15.0,
        "LIQUIDITY": 5.0,
        "COMMODITY": 0.0,
        "REAL_ESTATE": 0.0,
        "ALTERNATIVE_INVESTMENT": 0.0,
    },
}
_DEFAULT_CONCENTRATION_THRESHOLD: Final[float] = 25.0
_DISCLAIMER: Final[str] = "Analysis for informational purposes only. Not financial advice."


def _round_pct(value: float) -> float:
    return round(value, 2)


def _zero_allocation() -> dict[str, float]:
    return {asset_class: 0.0 for asset_class in _ASSET_CLASSES}


def _extract_holdings(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_holdings = payload.get("holdings")
    if not isinstance(raw_holdings, dict):
        return {}

    holdings: dict[str, dict[str, Any]] = {}
    for symbol, holding in raw_holdings.items():
        if isinstance(holding, dict) and isinstance(symbol, str):
            holdings[symbol] = holding

    return holdings


def _to_numeric_pct(value: Any) -> float:
    if isinstance(value, (int, float)):
        numeric_value = float(value)
        # Ghostfolio can return allocation ratios in the 0..1 range.
        if 0.0 <= numeric_value <= 1.0:
            return numeric_value * 100.0
        return numeric_value

    return 0.0


def _aggregate_current_allocation(
    holdings: dict[str, dict[str, Any]],
) -> tuple[dict[str, float], list[dict[str, float | str]], int]:
    current_allocation = _zero_allocation()
    concentration_warnings: list[dict[str, float | str]] = []

    for symbol, holding in holdings.items():
        asset_class = holding.get("assetClass")
        allocation_pct = _to_numeric_pct(holding.get("allocationInPercentage"))

        if isinstance(asset_class, str) and asset_class in current_allocation:
            current_allocation[asset_class] += allocation_pct
        else:
            # Some data sources omit asset class; classify as equity to preserve totals.
            current_allocation["EQUITY"] += allocation_pct

        if allocation_pct > _DEFAULT_CONCENTRATION_THRESHOLD:
            concentration_warnings.append(
                {
                    "symbol": symbol,
                    "pct_of_portfolio": _round_pct(allocation_pct),
                    "threshold": _round_pct(_DEFAULT_CONCENTRATION_THRESHOLD),
                }
            )

    total_allocation = sum(current_allocation.values())
    # Normalize only when upstream data omits/reshapes categories and drifts from ~100%.
    if total_allocation > 0.0 and abs(total_allocation - 100.0) > 1.0:
        current_allocation = {
            asset_class: (allocation / total_allocation) * 100.0
            for asset_class, allocation in current_allocation.items()
        }

    rounded_allocation = {
        asset_class: _round_pct(current_allocation[asset_class]) for asset_class in _ASSET_CLASSES
    }
    sorted_warnings = sorted(
        concentration_warnings,
        key=lambda warning: (
            -float(warning["pct_of_portfolio"]),
            str(warning["symbol"]),
        ),
    )
    return rounded_allocation, sorted_warnings, len(holdings)


def _format_asset_class(asset_class: str) -> str:
    return asset_class.replace("_", " ").title()


def _build_rebalancing_suggestions(drift: dict[str, float], target_profile: str) -> list[str]:
    suggestions: list[str] = []
    overweights = sorted(
        ((asset_class, value) for asset_class, value in drift.items() if value > 0),
        key=lambda item: (-item[1], item[0]),
    )
    underweights = sorted(
        ((asset_class, value) for asset_class, value in drift.items() if value < 0),
        key=lambda item: (item[1], item[0]),
    )

    if overweights:
        asset_class, value = overweights[0]
        suggestions.append(
            "Consider trimming "
            f"{_format_asset_class(asset_class)} by about {_round_pct(value)}% "
            f"to align with the {target_profile} profile."
        )

    if underweights:
        asset_class, value = underweights[0]
        suggestions.append(
            "Consider increasing "
            f"{_format_asset_class(asset_class)} by about {_round_pct(abs(value))}% "
            f"to align with the {target_profile} profile."
        )

    if not suggestions:
        suggestions.append("Current allocation is already close to the selected target profile.")

    return suggestions


async def advise_asset_allocation(
    api_client: GhostfolioClient, target_profile: str = "balanced"
) -> ToolResult:
    """Compares current allocation against a deterministic target profile.

    Args:
        api_client: Injected Ghostfolio API client.
        target_profile: One of "conservative", "balanced", or "aggressive".

    Returns:
        ToolResult with allocation drift insights or a structured error.
    """
    if target_profile not in _TARGET_ALLOCATIONS:
        return ToolResult.fail("INVALID_TARGET_PROFILE", target_profile=target_profile)

    try:
        details_payload = await api_client.get_portfolio_details()
        holdings = _extract_holdings(details_payload)
        if not holdings:
            return ToolResult.fail("EMPTY_PORTFOLIO", target_profile=target_profile)

        current_allocation, concentration_warnings, holdings_count = _aggregate_current_allocation(
            holdings
        )
        if holdings_count == 0:
            return ToolResult.fail("EMPTY_PORTFOLIO", target_profile=target_profile)

        target_allocation = {
            asset_class: _round_pct(_TARGET_ALLOCATIONS[target_profile][asset_class])
            for asset_class in _ASSET_CLASSES
        }
        drift = {
            asset_class: _round_pct(current_allocation[asset_class] - target_allocation[asset_class])
            for asset_class in _ASSET_CLASSES
        }
        rebalancing_suggestions = _build_rebalancing_suggestions(drift, target_profile)

        result_payload: dict[str, Any] = {
            "target_profile": target_profile,
            "current_allocation": current_allocation,
            "target_allocation": target_allocation,
            "drift": drift,
            "concentration_warnings": concentration_warnings,
            "rebalancing_suggestions": rebalancing_suggestions,
            "holdings_count": holdings_count,
            "disclaimer": _DISCLAIMER,
        }
        return ToolResult.ok(
            result_payload,
            source="allocation_advisor",
            target_profile=target_profile,
        )
    except GhostfolioClientError as error:
        metadata: dict[str, int | str] = {"target_profile": target_profile}
        if error.status is not None:
            metadata["status"] = error.status

        return ToolResult.fail(error.error_code, **metadata)
    except Exception:
        return ToolResult.fail("API_ERROR", target_profile=target_profile)
