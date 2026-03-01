"""Unit tests for the explore_prediction_markets tool and prediction_helpers."""

from __future__ import annotations

import pytest

from agent.clients.mock_client import MockGhostfolioClient
from agent.tools.prediction_helpers import (
    expected_value,
    implied_probability,
    kelly_fraction,
    market_efficiency_score,
    portfolio_exposure_pct,
)
from agent.tools.prediction_markets import explore_prediction_markets


@pytest.fixture()
def mock_client() -> MockGhostfolioClient:
    return MockGhostfolioClient()


# =====================================================================
# Existing tests (9)
# =====================================================================


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


# =====================================================================
# Helper tests (H1-H9) — pure functions, no mocks
# =====================================================================


def test_implied_probability_standard() -> None:
    """H1: Standard price converts to percentage."""
    assert implied_probability(0.65) == pytest.approx(65.0, abs=0.1)


def test_implied_probability_clamp_edges() -> None:
    """H2: Edge prices are clamped."""
    assert implied_probability(0.0) == pytest.approx(0.1, abs=0.1)
    assert implied_probability(1.0) == pytest.approx(99.9, abs=0.1)


def test_kelly_positive_edge() -> None:
    """H3: Positive edge yields a fraction between 0 and max."""
    result = kelly_fraction(0.6, 1.538, 10000)
    assert result["fraction"] > 0
    assert result["fraction"] <= 0.25
    assert result["amount"] > 0


def test_kelly_negative_ev() -> None:
    """H4: Negative EV yields zero fraction."""
    result = kelly_fraction(0.3, 1.1, 10000)
    assert result["fraction"] == 0.0
    assert result["amount"] == 0.0


def test_expected_value_profitable() -> None:
    """H5: Bet with positive EV is marked profitable."""
    result = expected_value(0.7, 1.0, 0.65)
    assert result["profitable"] is True
    assert result["ev"] > 0


def test_expected_value_unprofitable() -> None:
    """H6: Bet with negative EV is marked unprofitable."""
    result = expected_value(0.3, 1.0, 0.65)
    assert result["profitable"] is False
    assert result["ev"] < 0


def test_market_efficiency_liquid() -> None:
    """H7: High-volume, tight-spread market gets grade A or B (efficient)."""
    # spread=0.02, midpoint=0.65, spread_pct=3.08% → grade B (vol≥100k & spread≤5%)
    result = market_efficiency_score(0.64, 0.66, 1_250_000)
    assert result["liquidity_grade"] in ("A", "B")
    assert result["efficiency_rating"] == "efficient"
    # Truly grade A: spread ≤ 2%
    result_tight = market_efficiency_score(0.645, 0.655, 1_250_000)
    assert result_tight["liquidity_grade"] == "A"


def test_market_efficiency_illiquid() -> None:
    """H8: Low-volume, wide-spread market gets grade F."""
    result = market_efficiency_score(0.30, 0.70, 5_000)
    assert result["liquidity_grade"] == "F"
    assert result["efficiency_rating"] == "inefficient"


def test_portfolio_exposure_zero_networth() -> None:
    """H9: Zero net worth returns 0% exposure."""
    assert portfolio_exposure_pct(1000, 0) == 0.0


# =====================================================================
# Enrichment tests (E1-E2)
# =====================================================================


@pytest.mark.asyncio
async def test_browse_enriched_fields(mock_client: MockGhostfolioClient) -> None:
    """E1: Browse results include implied_probabilities and liquidity_grade."""
    result = await explore_prediction_markets(mock_client, action="browse")
    assert result.success
    for market in result.data["markets"]:
        assert "implied_probabilities" in market
        assert isinstance(market["implied_probabilities"], list)
        assert "liquidity_grade" in market


@pytest.mark.asyncio
async def test_positions_with_pnl(mock_client: MockGhostfolioClient) -> None:
    """E2: Positions include unrealized_pnl and exposure_pct."""
    result = await explore_prediction_markets(mock_client, action="positions")
    assert result.success
    assert "exposure_pct" in result.data
    for pos in result.data["positions"]:
        assert "unrealized_pnl" in pos
        assert "entry_price" in pos
        assert "current_price" in pos


# =====================================================================
# New action tests (A1-A7)
# =====================================================================


@pytest.mark.asyncio
async def test_simulate_valid(mock_client: MockGhostfolioClient) -> None:
    """A1: Simulate returns profit/loss, EV, Kelly, risk level."""
    result = await explore_prediction_markets(
        mock_client, action="simulate",
        market_slug="will-bitcoin-reach-100k-2026", amount=500, outcome="Yes",
    )
    assert result.success
    assert result.data["action"] == "simulate"
    assert "potential_profit" in result.data
    assert "potential_loss" in result.data
    assert "ev_analysis" in result.data
    assert "kelly_hint" in result.data
    assert "risk_level" in result.data


@pytest.mark.asyncio
async def test_simulate_invalid_slug(mock_client: MockGhostfolioClient) -> None:
    """A2: Simulate with unknown slug fails."""
    result = await explore_prediction_markets(
        mock_client, action="simulate",
        market_slug="nonexistent-slug", amount=500,
    )
    assert not result.success
    assert result.error == "MARKET_NOT_FOUND"


@pytest.mark.asyncio
async def test_simulate_invalid_amount(mock_client: MockGhostfolioClient) -> None:
    """A3: Simulate with invalid amount fails."""
    result = await explore_prediction_markets(
        mock_client, action="simulate",
        market_slug="will-bitcoin-reach-100k-2026", amount=-50,
    )
    assert not result.success
    assert result.error == "INVALID_SIMULATION_AMOUNT"


@pytest.mark.asyncio
async def test_trending(mock_client: MockGhostfolioClient) -> None:
    """A4: Trending returns markets sorted by volume desc."""
    result = await explore_prediction_markets(mock_client, action="trending")
    assert result.success
    assert result.data["action"] == "trending"
    trending = result.data["trending_markets"]
    assert len(trending) > 0
    # Check sorted by volume desc
    volumes = [m["volume_24h"] for m in trending]
    assert volumes == sorted(volumes, reverse=True)


@pytest.mark.asyncio
async def test_trending_by_category(mock_client: MockGhostfolioClient) -> None:
    """A5: Trending filtered by category."""
    result = await explore_prediction_markets(
        mock_client, action="trending", category="Crypto",
    )
    assert result.success
    for m in result.data["trending_markets"]:
        assert m["category"] == "Crypto"


@pytest.mark.asyncio
async def test_compare_two_markets(mock_client: MockGhostfolioClient) -> None:
    """A6: Compare returns markets and comparison_matrix."""
    result = await explore_prediction_markets(
        mock_client, action="compare",
        market_slugs=["will-bitcoin-reach-100k-2026", "fed-rate-cut-march-2026"],
    )
    assert result.success
    assert result.data["action"] == "compare"
    assert len(result.data["markets"]) == 2
    assert "comparison_matrix" in result.data
    matrix = result.data["comparison_matrix"]
    assert "spread_winner" in matrix
    assert "volume_winner" in matrix
    assert "efficiency_winner" in matrix


@pytest.mark.asyncio
async def test_compare_too_few(mock_client: MockGhostfolioClient) -> None:
    """A7: Compare with <2 slugs fails."""
    result = await explore_prediction_markets(
        mock_client, action="compare",
        market_slugs=["will-bitcoin-reach-100k-2026"],
    )
    assert not result.success
    assert result.error == "INVALID_COMPARISON_COUNT"


# =====================================================================
# Scenario action tests (S1-S11)
# =====================================================================


@pytest.mark.asyncio
async def test_scenario_percent_allocation(mock_client: MockGhostfolioClient) -> None:
    """S1: Percent allocation resolves correctly with win/lose cases."""
    result = await explore_prediction_markets(
        mock_client, action="scenario",
        market_slug="will-bitcoin-reach-100k-2026",
        allocation_mode="percent", allocation_value=20,
        outcome="Yes",
    )
    assert result.success
    data = result.data
    assert data["action"] == "scenario"
    assert data["allocation"]["mode"] == "percent"
    # Net worth is $13,750 → 20% = $2,750
    assert data["allocation"]["resolved_amount"] == pytest.approx(2750.0, abs=1)
    assert "win_case" in data["scenario_metrics"]
    assert "lose_case" in data["scenario_metrics"]


@pytest.mark.asyncio
async def test_scenario_fixed_allocation(mock_client: MockGhostfolioClient) -> None:
    """S2: Fixed allocation uses the input value directly."""
    result = await explore_prediction_markets(
        mock_client, action="scenario",
        market_slug="will-bitcoin-reach-100k-2026",
        allocation_mode="fixed", allocation_value=5000,
        outcome="Yes",
    )
    assert result.success
    assert result.data["allocation"]["resolved_amount"] == pytest.approx(5000.0, abs=1)


@pytest.mark.asyncio
async def test_scenario_all_in(mock_client: MockGhostfolioClient) -> None:
    """S3: All-in uses the full net worth."""
    result = await explore_prediction_markets(
        mock_client, action="scenario",
        market_slug="will-bitcoin-reach-100k-2026",
        allocation_mode="all_in",
        outcome="Yes",
    )
    assert result.success
    assert result.data["allocation"]["resolved_amount"] == pytest.approx(13750.0, abs=1)
    assert result.data["risk_assessment"]["risk_level"] == "high"


@pytest.mark.asyncio
async def test_scenario_slug_resolution_from_query(mock_client: MockGhostfolioClient) -> None:
    """S4: Slug resolved from search query when slug absent."""
    result = await explore_prediction_markets(
        mock_client, action="scenario",
        query="Bitcoin",
        allocation_mode="percent", allocation_value=10,
        outcome="Yes",
    )
    assert result.success
    assert result.data["market"]["slug"] != ""


@pytest.mark.asyncio
async def test_scenario_invalid_allocation_mode(mock_client: MockGhostfolioClient) -> None:
    """S5: Invalid allocation mode fails."""
    result = await explore_prediction_markets(
        mock_client, action="scenario",
        market_slug="will-bitcoin-reach-100k-2026",
        allocation_mode="yolo",
        allocation_value=20,
    )
    assert not result.success
    assert result.error == "INVALID_ALLOCATION_MODE"


@pytest.mark.asyncio
async def test_scenario_allocation_exceeds_portfolio(mock_client: MockGhostfolioClient) -> None:
    """S6: Allocation exceeding portfolio fails."""
    result = await explore_prediction_markets(
        mock_client, action="scenario",
        market_slug="will-bitcoin-reach-100k-2026",
        allocation_mode="percent", allocation_value=120,
        outcome="Yes",
    )
    assert not result.success
    assert result.error == "INVALID_ALLOCATION_VALUE"


@pytest.mark.asyncio
async def test_scenario_inactive_market(mock_client: MockGhostfolioClient) -> None:
    """S7: Inactive market fails with MARKET_INACTIVE."""
    result = await explore_prediction_markets(
        mock_client, action="scenario",
        market_slug="moon-landing-2025",
        allocation_mode="percent", allocation_value=10,
        outcome="Yes",
    )
    assert not result.success
    assert result.error == "MARKET_INACTIVE"


@pytest.mark.asyncio
async def test_scenario_tax_estimates_present(mock_client: MockGhostfolioClient) -> None:
    """S8: Scenario includes tax estimates."""
    result = await explore_prediction_markets(
        mock_client, action="scenario",
        market_slug="will-bitcoin-reach-100k-2026",
        allocation_mode="percent", allocation_value=20,
        outcome="Yes", income_bracket="middle",
    )
    assert result.success
    tax = result.data["tax_estimate"]
    assert "liquidation_tax" in tax
    assert "win_case_tax" in tax
    assert "rate_applied" in tax["liquidation_tax"]
    assert "rate_applied" in tax["win_case_tax"]


@pytest.mark.asyncio
async def test_scenario_concentration_flag_fires(mock_client: MockGhostfolioClient) -> None:
    """S9: Concentration flag fires when >25% of portfolio."""
    result = await explore_prediction_markets(
        mock_client, action="scenario",
        market_slug="will-bitcoin-reach-100k-2026",
        allocation_mode="percent", allocation_value=30,
        outcome="Yes",
    )
    assert result.success
    flags = result.data["compliance_flags"]
    assert any(f["type"] == "CONCENTRATION_RISK" for f in flags)


@pytest.mark.asyncio
async def test_scenario_allocation_drift_computed(mock_client: MockGhostfolioClient) -> None:
    """S10: Allocation drift is computed with proper keys."""
    result = await explore_prediction_markets(
        mock_client, action="scenario",
        market_slug="will-bitcoin-reach-100k-2026",
        allocation_mode="percent", allocation_value=20,
        outcome="Yes",
    )
    assert result.success
    drift = result.data["risk_assessment"]["allocation_drift"]
    assert "pre_trade" in drift
    assert "post_trade" in drift
    assert "drift_from_balanced" in drift


@pytest.mark.asyncio
async def test_scenario_empty_portfolio(mock_client: MockGhostfolioClient) -> None:
    """S11: Empty portfolio returns EMPTY_PORTFOLIO error."""
    empty_client = MockGhostfolioClient(
        portfolio_details={"summary": {"currentNetWorth": 0}},
        portfolio_holdings={"holdings": []},
    )
    result = await explore_prediction_markets(
        empty_client, action="scenario",
        market_slug="will-bitcoin-reach-100k-2026",
        allocation_mode="percent", allocation_value=20,
        outcome="Yes",
    )
    assert not result.success
    assert result.error == "EMPTY_PORTFOLIO"
