"""Portfolio Performance Analyzer tool."""

from __future__ import annotations

from agent.clients.ghostfolio_client import (
    VALID_DATE_RANGES,
    GhostfolioClient,
    GhostfolioClientError,
)
from agent.tools.base import ToolResult


async def analyze_portfolio_performance(
    api_client: GhostfolioClient, time_period: str = "max"
) -> ToolResult:
    """Retrieves portfolio performance for a supported date range.

    Args:
        api_client: Injected Ghostfolio API client.
        time_period: One of "1d", "wtd", "mtd", "ytd", "1y", "5y", "max".

    Returns:
        ToolResult with portfolio performance data or a structured error.
    """
    if time_period not in VALID_DATE_RANGES:
        return ToolResult.fail("INVALID_TIME_PERIOD", time_period=time_period)

    try:
        performance_payload = await api_client.get_portfolio_performance(time_period)
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
