"""Capital Gains Tax Estimator tool."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal

from agent.clients.ghostfolio_client import GhostfolioClient, GhostfolioClientError
from agent.tools.base import ToolResult

_VALID_INCOME_BRACKETS: Final[set[str]] = {"low", "middle", "high"}
_SHORT_TERM_CUTOFF_DAYS: Final[int] = 365
_DISCLAIMER: Final[str] = "Simplified estimate using FIFO. Not financial advice."
_TAX_RATES_BY_BRACKET: Final[dict[str, dict[str, float]]] = {
    "low": {"short_term": 0.22, "long_term": 0.0},
    "middle": {"short_term": 0.24, "long_term": 0.15},
    "high": {"short_term": 0.24, "long_term": 0.20},
}


@dataclass
class _OrderActivity:
    symbol: str
    activity_type: Literal["BUY", "SELL"]
    date: datetime
    quantity: float
    unit_price: float


@dataclass
class _BuyLot:
    acquired_at: datetime
    remaining_quantity: float
    unit_price: float


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_symbol(activity: dict[str, Any]) -> str | None:
    symbol_profile = activity.get("SymbolProfile")
    if isinstance(symbol_profile, dict):
        symbol = symbol_profile.get("symbol")
        if isinstance(symbol, str) and symbol.strip():
            return symbol.strip()

    return None


def _to_positive_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        numeric_value = float(value)
        if numeric_value > 0:
            return numeric_value

    return None


def _to_non_negative_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        numeric_value = float(value)
        if numeric_value >= 0:
            return numeric_value

    return None


def _normalize_activities(raw_activities: list[Any]) -> list[_OrderActivity]:
    normalized: list[_OrderActivity] = []
    for raw_activity in raw_activities:
        if not isinstance(raw_activity, dict):
            continue

        activity_type = raw_activity.get("type")
        if activity_type not in {"BUY", "SELL"}:
            continue

        symbol = _extract_symbol(raw_activity)
        if symbol is None:
            continue

        activity_date = _parse_datetime(raw_activity.get("date"))
        quantity = _to_positive_float(raw_activity.get("quantity"))
        unit_price = _to_non_negative_float(raw_activity.get("unitPrice"))
        if activity_date is None or quantity is None or unit_price is None:
            continue

        normalized.append(
            _OrderActivity(
                symbol=symbol,
                activity_type=activity_type,
                date=activity_date,
                quantity=quantity,
                unit_price=unit_price,
            )
        )

    return normalized


def _round_money(value: float) -> float:
    return round(value, 2)


def _create_term_summary(
    rate_applied: float, realized_entries: list[dict[str, Any]]
) -> dict[str, float]:
    gains = _round_money(
        sum(entry["gain_loss"] for entry in realized_entries if entry["gain_loss"] > 0)
    )
    losses = _round_money(
        sum(entry["gain_loss"] for entry in realized_entries if entry["gain_loss"] < 0)
    )
    net = _round_money(gains + losses)
    estimated_tax = _round_money(max(net, 0.0) * rate_applied)

    return {
        "total_gains": gains,
        "total_losses": losses,
        "net": net,
        "estimated_tax": estimated_tax,
        "rate_applied": rate_applied,
    }


async def estimate_capital_gains_tax(
    api_client: GhostfolioClient, tax_year: int = 2025, income_bracket: str = "middle"
) -> ToolResult:
    """Estimates annual capital gains tax with FIFO lot matching.

    Args:
        api_client: Injected Ghostfolio API client.
        tax_year: Tax year to estimate, from 2020 through the current year.
        income_bracket: One of "low", "middle", or "high".

    Returns:
        ToolResult with tax estimate payload or structured error metadata.
    """
    current_year = datetime.now().year
    if tax_year < 2020 or tax_year > current_year:
        return ToolResult.fail("INVALID_TAX_YEAR", tax_year=tax_year)

    if income_bracket not in _VALID_INCOME_BRACKETS:
        return ToolResult.fail("INVALID_INCOME_BRACKET", income_bracket=income_bracket)

    try:
        orders_payload = await api_client.get_orders()
        raw_activities = orders_payload.get("activities", [])
        if not isinstance(raw_activities, list):
            return ToolResult.fail(
                "API_ERROR",
                tax_year=tax_year,
                income_bracket=income_bracket,
            )

        normalized_activities = _normalize_activities(raw_activities)
        activities_by_symbol: dict[str, list[_OrderActivity]] = {}
        for activity in normalized_activities:
            activities_by_symbol.setdefault(activity.symbol, []).append(activity)

        per_asset_entries: list[dict[str, Any]] = []
        for symbol in sorted(activities_by_symbol):
            ordered_activities = sorted(
                activities_by_symbol[symbol],
                key=lambda entry: entry.date,
            )
            available_lots: deque[_BuyLot] = deque()

            for activity in ordered_activities:
                if activity.activity_type == "BUY":
                    available_lots.append(
                        _BuyLot(
                            acquired_at=activity.date,
                            remaining_quantity=activity.quantity,
                            unit_price=activity.unit_price,
                        )
                    )
                    continue

                remaining_to_match = activity.quantity
                while remaining_to_match > 0 and available_lots:
                    oldest_lot = available_lots[0]
                    matched_quantity = min(remaining_to_match, oldest_lot.remaining_quantity)
                    cost_basis = matched_quantity * oldest_lot.unit_price
                    proceeds = matched_quantity * activity.unit_price
                    gain_loss = proceeds - cost_basis

                    oldest_lot.remaining_quantity -= matched_quantity
                    remaining_to_match -= matched_quantity
                    if oldest_lot.remaining_quantity <= 0:
                        available_lots.popleft()

                    if activity.date.year != tax_year:
                        continue

                    holding_days = (activity.date - oldest_lot.acquired_at).days
                    holding_period = (
                        "long_term"
                        if holding_days > _SHORT_TERM_CUTOFF_DAYS
                        else "short_term"
                    )

                    per_asset_entries.append(
                        {
                            "symbol": symbol,
                            "gain_loss": _round_money(gain_loss),
                            "holding_period": holding_period,
                            "cost_basis": _round_money(cost_basis),
                            "proceeds": _round_money(proceeds),
                        }
                    )

        short_term_entries = [
            entry for entry in per_asset_entries if entry["holding_period"] == "short_term"
        ]
        long_term_entries = [
            entry for entry in per_asset_entries if entry["holding_period"] == "long_term"
        ]
        rates = _TAX_RATES_BY_BRACKET[income_bracket]
        short_term_summary = _create_term_summary(rates["short_term"], short_term_entries)
        long_term_summary = _create_term_summary(rates["long_term"], long_term_entries)

        result_payload: dict[str, Any] = {
            "tax_year": tax_year,
            "income_bracket": income_bracket,
            "short_term": short_term_summary,
            "long_term": long_term_summary,
            "combined_liability": _round_money(
                short_term_summary["estimated_tax"] + long_term_summary["estimated_tax"]
            ),
            "per_asset": per_asset_entries,
            "disclaimer": _DISCLAIMER,
        }

        return ToolResult.ok(
            result_payload,
            source="capital_gains_tax_estimator",
            tax_year=tax_year,
            income_bracket=income_bracket,
        )
    except GhostfolioClientError as error:
        metadata: dict[str, int | str] = {
            "tax_year": tax_year,
            "income_bracket": income_bracket,
        }
        if error.status is not None:
            metadata["status"] = error.status

        return ToolResult.fail(error.error_code, **metadata)
    except Exception:
        return ToolResult.fail(
            "API_ERROR",
            tax_year=tax_year,
            income_bracket=income_bracket,
        )
