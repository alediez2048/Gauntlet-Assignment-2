"""Market Data tool — fetches current prices and metrics for portfolio holdings."""

from __future__ import annotations

from typing import Any, Final

from agent.clients.ghostfolio_client import GhostfolioClient, GhostfolioClientError
from agent.tools.base import ToolResult

_VALID_METRICS: Final[set[str]] = {
    "price",
    "change",
    "change_percent",
    "currency",
    "market_value",
    "quantity",
    "all",
}
_DEFAULT_METRICS: Final[list[str]] = ["price", "change", "change_percent", "currency", "market_value"]
_DISCLAIMER: Final[str] = "Market data sourced from Ghostfolio portfolio. Prices may be delayed."


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_holding_data(
    symbol: str,
    holding: dict[str, Any],
    metrics: list[str],
) -> dict[str, Any]:
    """Extract requested metrics from a single holding."""
    entry: dict[str, Any] = {"symbol": symbol}
    use_all = "all" in metrics

    if use_all or "price" in metrics:
        entry["price"] = _to_float(
            holding.get("marketPrice")
            or holding.get("averagePrice")
            or holding.get("unitPrice")
        )

    if use_all or "change" in metrics:
        entry["change"] = _to_float(holding.get("netPerformance"))

    if use_all or "change_percent" in metrics:
        pct = _to_float(holding.get("netPerformancePercentage"))
        if pct is not None and -1.0 <= pct <= 100.0:
            pct = round(pct * 100, 2)
        entry["change_percent"] = pct

    if use_all or "currency" in metrics:
        entry["currency"] = holding.get("currency") or "USD"

    if use_all or "market_value" in metrics:
        entry["market_value"] = _to_float(
            holding.get("value")
            or holding.get("marketValue")
        )

    if use_all or "quantity" in metrics:
        entry["quantity"] = _to_float(holding.get("quantity"))

    entry["name"] = holding.get("name") or symbol
    entry["asset_class"] = holding.get("assetClass") or "UNKNOWN"
    entry["asset_sub_class"] = holding.get("assetSubClass") or "UNKNOWN"

    return entry


async def get_market_data(
    api_client: GhostfolioClient,
    symbols: list[str] | None = None,
    metrics: list[str] | None = None,
) -> ToolResult:
    """Fetch current market data for portfolio holdings.

    Args:
        api_client: Injected Ghostfolio API client.
        symbols: Optional list of symbols to filter. Defaults to all holdings.
        metrics: Requested data points. Defaults to price, change, change_percent,
                 currency, market_value.

    Returns:
        ToolResult with per-symbol market data or a structured error.
    """
    resolved_metrics = list(metrics) if metrics else list(_DEFAULT_METRICS)
    for m in resolved_metrics:
        if m not in _VALID_METRICS:
            return ToolResult.fail(
                "INVALID_METRIC",
                requested_metric=m,
                valid_metrics=list(_VALID_METRICS),
            )

    try:
        details_payload = await api_client.get_portfolio_details()
        raw_holdings = details_payload.get("holdings")
        if not isinstance(raw_holdings, dict) or not raw_holdings:
            return ToolResult.fail("EMPTY_PORTFOLIO")

        resolved_symbols: list[str] | None = None
        if symbols:
            upper_symbols = {s.upper() for s in symbols if isinstance(s, str)}
            if upper_symbols:
                resolved_symbols = list(upper_symbols)

        results: list[dict[str, Any]] = []
        total_market_value = 0.0

        for symbol, holding in raw_holdings.items():
            if not isinstance(holding, dict):
                continue
            if resolved_symbols and symbol.upper() not in resolved_symbols:
                continue
            entry = _extract_holding_data(symbol, holding, resolved_metrics)
            results.append(entry)
            mv = _to_float(holding.get("value") or holding.get("marketValue"))
            if mv is not None:
                total_market_value += mv

        if not results:
            if resolved_symbols:
                return ToolResult.fail(
                    "SYMBOLS_NOT_FOUND",
                    requested_symbols=resolved_symbols,
                )
            return ToolResult.fail("EMPTY_PORTFOLIO")

        results.sort(key=lambda r: -(r.get("market_value") or 0))

        return ToolResult.ok(
            {
                "holdings": results,
                "total_holdings": len(results),
                "total_market_value": round(total_market_value, 2),
                "metrics_requested": resolved_metrics,
                "disclaimer": _DISCLAIMER,
            },
            source="market_data",
        )
    except GhostfolioClientError as error:
        metadata: dict[str, int | str] = {}
        if error.status is not None:
            metadata["status"] = error.status
        return ToolResult.fail(error.error_code, **metadata)
    except Exception:
        return ToolResult.fail("API_ERROR")
