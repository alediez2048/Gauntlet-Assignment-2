"""Portfolio Performance Analyzer tool.

Uses the ``/api/v1/portfolio/details`` endpoint so that the numbers shown by the
agent match what the Ghostfolio dashboard displays.  The ``summary`` block is
re-shaped into a ``performance`` key so downstream validators, citation
extractors, and the LLM synthesizer continue to work unchanged.
"""

from __future__ import annotations

from typing import Any

from agent.clients.ghostfolio_client import (
    VALID_DATE_RANGES,
    GhostfolioClient,
    GhostfolioClientError,
)
from agent.tools.base import ToolResult


def _reshape_details_to_performance(details: dict[str, Any]) -> dict[str, Any]:
    """Extract and reshape the details summary into the performance format.

    Maps the ``summary`` block from ``/api/v1/portfolio/details`` into the
    ``performance`` key structure that the rest of the agent pipeline expects.
    """
    summary = details.get("summary") or {}
    return {
        "performance": {
            "currentNetWorth": summary.get("currentNetWorth", 0),
            "currentValueInBaseCurrency": summary.get("currentValueInBaseCurrency", 0),
            "netPerformance": summary.get("netPerformance", 0),
            "netPerformancePercentage": summary.get("netPerformancePercentage", 0),
            "netPerformancePercentageWithCurrencyEffect": summary.get(
                "netPerformancePercentageWithCurrencyEffect", 0
            ),
            "netPerformanceWithCurrencyEffect": summary.get("netPerformanceWithCurrencyEffect", 0),
            "totalInvestment": summary.get("totalInvestment", 0),
            "totalInvestmentValueWithCurrencyEffect": summary.get(
                "totalInvestmentValueWithCurrencyEffect", 0
            ),
        },
        "hasErrors": False,
    }


async def analyze_portfolio_performance(
    api_client: GhostfolioClient, time_period: str = "max"
) -> ToolResult:
    """Retrieves portfolio performance from the details endpoint.

    Uses ``/api/v1/portfolio/details`` (the same source as the Ghostfolio
    dashboard) so that the agent's numbers match what the user sees in the UI.

    Args:
        api_client: Injected Ghostfolio API client.
        time_period: Accepted for interface compatibility but not used in the
            API call.  Validated to keep the error contract intact.

    Returns:
        ToolResult with portfolio performance data or a structured error.
    """
    if time_period not in VALID_DATE_RANGES:
        return ToolResult.fail("INVALID_TIME_PERIOD", time_period=time_period)

    try:
        details_payload = await api_client.get_portfolio_details()
        performance_payload = _reshape_details_to_performance(details_payload)
        return ToolResult.ok(
            performance_payload,
            source="portfolio_performance",
            time_period=time_period,
        )
    except GhostfolioClientError as error:
        metadata: dict[str, int | str] = {"time_period": time_period}
        if error.status is not None:
            metadata["status"] = error.status

        return ToolResult.fail(error.error_code, **metadata)
    except Exception:
        return ToolResult.fail("API_ERROR", time_period=time_period)
