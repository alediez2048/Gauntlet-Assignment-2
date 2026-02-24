from typing import Any

import pytest

from agent.clients.ghostfolio_client import GhostfolioClientError
from agent.clients.mock_client import MockGhostfolioClient
from agent.tools.portfolio_analyzer import analyze_portfolio_performance


class SpyPerformanceClient:
    def __init__(self) -> None:
        self.call_count = 0

    async def get_portfolio_performance(self, time_period: str) -> dict[str, Any]:
        self.call_count += 1
        return {"performance": {"netPerformance": 1}}


class ErroringPerformanceClient:
    def __init__(self, error: Exception) -> None:
        self.call_count = 0
        self.error = error

    async def get_portfolio_performance(self, time_period: str) -> dict[str, Any]:
        self.call_count += 1
        raise self.error


@pytest.mark.asyncio
async def test_analyze_portfolio_performance_happy_path(
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    result = await analyze_portfolio_performance(mock_ghostfolio_client, time_period="ytd")

    assert result.success is True
    assert result.error is None
    assert result.data is not None
    assert "performance" in result.data
    assert "chart" in result.data
    assert result.metadata["source"] == "portfolio_performance"
    assert result.metadata["time_period"] == "ytd"


@pytest.mark.asyncio
async def test_analyze_portfolio_performance_invalid_period_short_circuits_api_call() -> None:
    spy_client = SpyPerformanceClient()

    result = await analyze_portfolio_performance(spy_client, time_period="monthly")

    assert result.success is False
    assert result.data is None
    assert result.error == "INVALID_TIME_PERIOD"
    assert result.metadata["time_period"] == "monthly"
    assert spy_client.call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_code", "status"),
    [("API_TIMEOUT", None), ("API_ERROR", 500), ("AUTH_FAILED", 401)],
)
async def test_analyze_portfolio_performance_maps_client_error_codes(
    error_code: str, status: int | None
) -> None:
    failing_client = ErroringPerformanceClient(
        GhostfolioClientError(error_code, status=status, detail="internal detail")
    )

    result = await analyze_portfolio_performance(failing_client, time_period="ytd")

    assert result.success is False
    assert result.data is None
    assert result.error == error_code
    assert result.metadata["time_period"] == "ytd"
    if status is None:
        assert "status" not in result.metadata
    else:
        assert result.metadata["status"] == status
    assert "internal detail" not in str(result.metadata)


@pytest.mark.asyncio
async def test_analyze_portfolio_performance_maps_unexpected_exceptions_to_api_error() -> None:
    failing_client = ErroringPerformanceClient(RuntimeError("unexpected low-level detail"))

    result = await analyze_portfolio_performance(failing_client, time_period="ytd")

    assert result.success is False
    assert result.data is None
    assert result.error == "API_ERROR"
    assert result.metadata["time_period"] == "ytd"
    assert "unexpected low-level detail" not in str(result.metadata)
