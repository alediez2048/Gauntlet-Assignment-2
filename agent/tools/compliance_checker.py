"""Compliance Check tool — scans transactions for regulatory red flags."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Final

from agent.clients.ghostfolio_client import GhostfolioClient, GhostfolioClientError
from agent.tools.base import ToolResult

_WASH_SALE_WINDOW_DAYS: Final[int] = 30
_PATTERN_DAY_TRADE_THRESHOLD: Final[int] = 4
_PATTERN_DAY_TRADE_WINDOW_DAYS: Final[int] = 5
_CONCENTRATION_THRESHOLD_PCT: Final[float] = 25.0
_DISCLAIMER: Final[str] = (
    "Informational screening only — not legal or tax advice. "
    "Consult a qualified professional for compliance decisions."
)

_VALID_CHECK_TYPES: Final[set[str]] = {"all", "wash_sale", "pattern_day_trading", "concentration"}


def _parse_date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _extract_symbol(activity: dict[str, Any]) -> str:
    symbol = activity.get("SymbolProfile", {}).get("symbol") if isinstance(activity.get("SymbolProfile"), dict) else None
    if not symbol:
        symbol = activity.get("symbol")
    return str(symbol) if symbol else "UNKNOWN"


def _extract_type(activity: dict[str, Any]) -> str:
    return str(activity.get("type", "")).upper()


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _detect_wash_sales(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect potential wash sale violations (sell at loss + repurchase within 30 days)."""
    sells: list[dict[str, Any]] = []
    buys: list[dict[str, Any]] = []

    for act in activities:
        act_type = _extract_type(act)
        act_date = _parse_date(act.get("date"))
        if act_date is None:
            continue
        entry = {
            "symbol": _extract_symbol(act),
            "date": act_date,
            "quantity": _to_float(act.get("quantity")),
            "unit_price": _to_float(act.get("unitPrice")),
            "fee": _to_float(act.get("fee")),
        }
        if act_type == "SELL":
            sells.append(entry)
        elif act_type == "BUY":
            buys.append(entry)

    violations: list[dict[str, Any]] = []
    for sell in sells:
        for buy in buys:
            if buy["symbol"] != sell["symbol"]:
                continue
            days_diff = (buy["date"] - sell["date"]).days
            if 0 < days_diff <= _WASH_SALE_WINDOW_DAYS:
                violations.append({
                    "type": "WASH_SALE",
                    "symbol": sell["symbol"],
                    "sell_date": sell["date"].strftime("%Y-%m-%d"),
                    "rebuy_date": buy["date"].strftime("%Y-%m-%d"),
                    "days_between": days_diff,
                    "description": (
                        f"Sold {sell['symbol']} on {sell['date'].strftime('%Y-%m-%d')} "
                        f"and repurchased on {buy['date'].strftime('%Y-%m-%d')} "
                        f"({days_diff} days later, within {_WASH_SALE_WINDOW_DAYS}-day window)."
                    ),
                })
    return violations


def _detect_pattern_day_trading(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect potential pattern day trading (4+ day trades in 5 business days)."""
    day_trades_by_date: dict[str, list[str]] = {}

    buys_by_symbol_date: dict[tuple[str, str], int] = {}
    sells_by_symbol_date: dict[tuple[str, str], int] = {}

    for act in activities:
        act_type = _extract_type(act)
        act_date = _parse_date(act.get("date"))
        if act_date is None or act_type not in ("BUY", "SELL"):
            continue
        symbol = _extract_symbol(act)
        date_str = act_date.strftime("%Y-%m-%d")
        key = (symbol, date_str)
        if act_type == "BUY":
            buys_by_symbol_date[key] = buys_by_symbol_date.get(key, 0) + 1
        else:
            sells_by_symbol_date[key] = sells_by_symbol_date.get(key, 0) + 1

    for (symbol, date_str), buy_count in buys_by_symbol_date.items():
        sell_count = sells_by_symbol_date.get((symbol, date_str), 0)
        if buy_count > 0 and sell_count > 0:
            if date_str not in day_trades_by_date:
                day_trades_by_date[date_str] = []
            day_trades_by_date[date_str].append(symbol)

    warnings: list[dict[str, Any]] = []
    sorted_dates = sorted(day_trades_by_date.keys())

    for i, date_str in enumerate(sorted_dates):
        window_start = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=_PATTERN_DAY_TRADE_WINDOW_DAYS)
        window_start_str = window_start.strftime("%Y-%m-%d")
        trade_count = 0
        symbols_in_window: list[str] = []
        for check_date in sorted_dates:
            if window_start_str <= check_date <= date_str:
                trade_count += len(day_trades_by_date[check_date])
                symbols_in_window.extend(day_trades_by_date[check_date])

        if trade_count >= _PATTERN_DAY_TRADE_THRESHOLD:
            warnings.append({
                "type": "PATTERN_DAY_TRADING",
                "window_end": date_str,
                "day_trades_in_window": trade_count,
                "symbols": list(set(symbols_in_window)),
                "description": (
                    f"{trade_count} day trade(s) detected in the "
                    f"{_PATTERN_DAY_TRADE_WINDOW_DAYS}-day window ending {date_str}. "
                    f"FINRA flags accounts with {_PATTERN_DAY_TRADE_THRESHOLD}+ day trades "
                    f"in 5 business days as pattern day traders."
                ),
            })
            break  # one warning is sufficient

    return warnings


def _detect_concentration_risk(
    holdings: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Flag any single position exceeding the concentration threshold."""
    warnings: list[dict[str, Any]] = []
    total_value = 0.0
    position_values: list[tuple[str, float]] = []

    for symbol, holding in holdings.items():
        value = _to_float(holding.get("value") or holding.get("marketValue") or 0)
        total_value += value
        position_values.append((symbol, value))

    if total_value <= 0:
        return warnings

    for symbol, value in position_values:
        pct = (value / total_value) * 100.0
        if pct > _CONCENTRATION_THRESHOLD_PCT:
            warnings.append({
                "type": "CONCENTRATION",
                "symbol": symbol,
                "pct_of_portfolio": round(pct, 2),
                "threshold": _CONCENTRATION_THRESHOLD_PCT,
                "description": (
                    f"{symbol} represents {pct:.1f}% of portfolio value, "
                    f"exceeding the {_CONCENTRATION_THRESHOLD_PCT}% concentration threshold."
                ),
            })

    return sorted(warnings, key=lambda w: -w["pct_of_portfolio"])


async def check_compliance(
    api_client: GhostfolioClient,
    check_type: str = "all",
) -> ToolResult:
    """Screen the portfolio for common regulatory red flags.

    Args:
        api_client: Injected Ghostfolio API client.
        check_type: One of "all", "wash_sale", "pattern_day_trading", "concentration".

    Returns:
        ToolResult with violations and warnings, or a structured error.
    """
    if check_type not in _VALID_CHECK_TYPES:
        return ToolResult.fail("INVALID_CHECK_TYPE", check_type=check_type)

    try:
        violations: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        if check_type in ("all", "wash_sale", "pattern_day_trading"):
            orders_payload = await api_client.get_orders()
            activities = orders_payload.get("activities", [])
            if not isinstance(activities, list):
                activities = []

            if check_type in ("all", "wash_sale"):
                violations.extend(_detect_wash_sales(activities))

            if check_type in ("all", "pattern_day_trading"):
                warnings.extend(_detect_pattern_day_trading(activities))

        if check_type in ("all", "concentration"):
            details_payload = await api_client.get_portfolio_details()
            raw_holdings = details_payload.get("holdings")
            holdings = (
                {k: v for k, v in raw_holdings.items() if isinstance(v, dict)}
                if isinstance(raw_holdings, dict)
                else {}
            )
            if holdings:
                warnings.extend(_detect_concentration_risk(holdings))

        return ToolResult.ok(
            {
                "check_type": check_type,
                "violations": violations,
                "warnings": warnings,
                "total_violations": len(violations),
                "total_warnings": len(warnings),
                "disclaimer": _DISCLAIMER,
            },
            source="compliance_checker",
            check_type=check_type,
        )
    except GhostfolioClientError as error:
        metadata: dict[str, int | str] = {"check_type": check_type}
        if error.status is not None:
            metadata["status"] = error.status
        return ToolResult.fail(error.error_code, **metadata)
    except Exception:
        return ToolResult.fail("API_ERROR", check_type=check_type)
