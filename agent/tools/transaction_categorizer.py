"""Transaction Categorizer tool."""

from __future__ import annotations

from typing import Any, Final

from agent.clients.ghostfolio_client import (
    VALID_DATE_RANGES,
    GhostfolioClient,
    GhostfolioClientError,
)
from agent.tools.base import ToolResult

_ACTIVITY_TYPES: Final[tuple[str, ...]] = (
    "BUY",
    "SELL",
    "DIVIDEND",
    "FEE",
    "INTEREST",
    "LIABILITY",
)


def _get_activity_value(activity: dict[str, Any]) -> float:
    """Returns a normalized numeric activity value."""
    value = activity.get("value")
    if isinstance(value, (int, float)):
        return float(value)

    quantity = activity.get("quantity")
    unit_price = activity.get("unitPrice")
    if isinstance(quantity, (int, float)) and isinstance(unit_price, (int, float)):
        return float(quantity) * float(unit_price)

    return 0.0


def _sum_activity_values(activities: list[dict[str, Any]]) -> float:
    """Sums activity values for a grouped category."""
    return round(sum(_get_activity_value(activity) for activity in activities), 2)


async def categorize_transactions(
    api_client: GhostfolioClient, date_range: str = "max"
) -> ToolResult:
    """Retrieves and categorizes transactions for a supported date range.

    Args:
        api_client: Injected Ghostfolio API client.
        date_range: One of "1d", "wtd", "mtd", "ytd", "1y", "5y", "max".

    Returns:
        ToolResult with grouped transaction activity data or a structured error.
    """
    if date_range not in VALID_DATE_RANGES:
        return ToolResult.fail("INVALID_TIME_PERIOD", date_range=date_range)

    try:
        orders_payload = await api_client.get_orders(date_range=date_range)
        raw_activities = orders_payload.get("activities", [])
        if not isinstance(raw_activities, list):
            return ToolResult.fail("API_ERROR", date_range=date_range)

        grouped_activities: dict[str, list[dict[str, Any]]] = {
            activity_type: [] for activity_type in _ACTIVITY_TYPES
        }

        for activity in raw_activities:
            if not isinstance(activity, dict):
                continue

            activity_type = activity.get("type")
            if activity_type in grouped_activities:
                grouped_activities[activity_type].append(activity)

        by_type_counts = {
            activity_type: len(grouped_activities[activity_type])
            for activity_type in _ACTIVITY_TYPES
        }

        result_payload: dict[str, Any] = {
            "total_transactions": len(raw_activities),
            "by_type": grouped_activities,
            "by_type_counts": by_type_counts,
            "summary": {
                "buy_total": _sum_activity_values(grouped_activities["BUY"]),
                "sell_total": _sum_activity_values(grouped_activities["SELL"]),
                "dividend_total": _sum_activity_values(grouped_activities["DIVIDEND"]),
                "interest_total": _sum_activity_values(grouped_activities["INTEREST"]),
                "fee_total": _sum_activity_values(grouped_activities["FEE"]),
                "liability_total": _sum_activity_values(grouped_activities["LIABILITY"]),
            },
        }

        count = orders_payload.get("count")
        if isinstance(count, int):
            result_payload["reported_count"] = count

        return ToolResult.ok(
            result_payload,
            source="transaction_categorizer",
            date_range=date_range,
        )
    except GhostfolioClientError as error:
        metadata: dict[str, int | str] = {"date_range": date_range}
        if error.status is not None:
            metadata["status"] = error.status

        return ToolResult.fail(error.error_code, **metadata)
    except Exception:
        return ToolResult.fail("API_ERROR", date_range=date_range)
