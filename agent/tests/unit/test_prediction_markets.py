"""Unit tests for the explore_prediction_markets tool."""

from __future__ import annotations

import pytest

from agent.clients.mock_client import MockGhostfolioClient
from agent.tools.prediction_markets import explore_prediction_markets


@pytest.fixture()
def mock_client() -> MockGhostfolioClient:
    return MockGhostfolioClient()


@pytest.mark.asyncio
async def test_browse_returns_markets(mock_client: MockGhostfolioClient) -> None:
    result = await explore_prediction_markets(mock_client, action="browse")
    assert result.success
    assert result.data is not None
    assert result.data["action"] == "browse"
    assert result.data["total_markets"] > 0
    markets = result.data["markets"]
    assert isinstance(markets, list)
    assert all("question" in m for m in markets)
    assert all("slug" in m for m in markets)
    assert all("outcomes" in m for m in markets)


@pytest.mark.asyncio
async def test_search_filters_markets(mock_client: MockGhostfolioClient) -> None:
    result = await explore_prediction_markets(mock_client, action="search", query="Bitcoin")
    assert result.success
    assert result.data is not None
    assert result.data["action"] == "search"
    markets = result.data["markets"]
    assert len(markets) > 0
    assert all("bitcoin" in m["question"].lower() for m in markets)


@pytest.mark.asyncio
async def test_search_no_results(mock_client: MockGhostfolioClient) -> None:
    result = await explore_prediction_markets(mock_client, action="search", query="zzzznonexistent")
    assert not result.success
    assert result.error == "NO_MARKETS_FOUND"


@pytest.mark.asyncio
async def test_browse_by_category(mock_client: MockGhostfolioClient) -> None:
    result = await explore_prediction_markets(mock_client, action="browse", category="Crypto")
    assert result.success
    assert result.data is not None
    markets = result.data["markets"]
    assert len(markets) > 0
    assert all(m["category"] == "Crypto" for m in markets)


@pytest.mark.asyncio
async def test_analyze_market(mock_client: MockGhostfolioClient) -> None:
    result = await explore_prediction_markets(
        mock_client, action="analyze", market_slug="will-bitcoin-reach-100k-2026"
    )
    assert result.success
    assert result.data is not None
    assert result.data["action"] == "analyze"
    assert result.data["question"] == "Will Bitcoin reach $100k by end of 2026?"
    assert "outcomes" in result.data
    assert "volume_24h" in result.data


@pytest.mark.asyncio
async def test_analyze_unknown_slug(mock_client: MockGhostfolioClient) -> None:
    result = await explore_prediction_markets(
        mock_client, action="analyze", market_slug="nonexistent-slug"
    )
    assert not result.success
    assert result.error == "MARKET_NOT_FOUND"


@pytest.mark.asyncio
async def test_positions(mock_client: MockGhostfolioClient) -> None:
    result = await explore_prediction_markets(mock_client, action="positions")
    assert result.success
    assert result.data is not None
    assert result.data["action"] == "positions"
    assert result.data["total_positions"] > 0
    positions = result.data["positions"]
    assert isinstance(positions, list)
    assert all("slug" in p for p in positions)


@pytest.mark.asyncio
async def test_outcome_prices_parsed(mock_client: MockGhostfolioClient) -> None:
    """Outcome prices stored as JSON strings should be parsed correctly."""
    result = await explore_prediction_markets(mock_client, action="browse")
    assert result.success
    markets = result.data["markets"]
    for market in markets:
        for outcome in market["outcomes"]:
            assert "label" in outcome
            assert "price" in outcome
            assert isinstance(outcome["price"], (int, float))


@pytest.mark.asyncio
async def test_disclaimer_present(mock_client: MockGhostfolioClient) -> None:
    result = await explore_prediction_markets(mock_client, action="browse")
    assert result.success
    assert "disclaimer" in result.data
