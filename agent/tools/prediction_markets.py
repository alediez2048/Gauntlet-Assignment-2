"""Prediction Markets tool — browse, search, analyze, simulate, trending, compare, scenario."""

from __future__ import annotations

from typing import Any

from agent.tools.base import ToolResult
from agent.tools.prediction_helpers import (
    compute_scenario,
    expected_value,
    format_market_summary,
    implied_probability,
    kelly_fraction,
    market_efficiency_score,
    portfolio_exposure_pct,
    risk_level,
    _SCENARIO_DISCLAIMER,
)


async def explore_prediction_markets(
    api_client: Any,
    action: str = "browse",
    query: str | None = None,
    category: str | None = None,
    market_slug: str | None = None,
    amount: float | None = None,
    outcome: str | None = None,
    market_slugs: list[str] | None = None,
    allocation_mode: str | None = None,
    allocation_value: float | None = None,
    time_horizon: str | None = None,
    income_bracket: str | None = None,
) -> ToolResult:
    """Browse, search, analyze, simulate, compare, or model prediction markets.

    Args:
        api_client: Injected Ghostfolio/mock API client.
        action: One of browse, search, analyze, positions, simulate, trending, compare, scenario.
        query: Search query for filtering markets.
        category: Category filter (e.g. "Crypto", "Politics").
        market_slug: Specific market slug for analysis/simulate/scenario.
        amount: Dollar amount for simulate action.
        outcome: "Yes" or "No" for simulate/scenario.
        market_slugs: List of slugs for compare action.
        allocation_mode: "fixed", "percent", or "all_in" for scenario.
        allocation_value: Dollar or percent value for scenario.
        time_horizon: "1m", "3m", "6m", "1y" for scenario.
        income_bracket: "low", "middle", "high" for scenario tax.

    Returns:
        ToolResult with market data or structured error.
    """
    try:
        if action == "positions":
            return await _handle_positions(api_client)
        if action == "analyze" and market_slug:
            return await _handle_analyze(api_client, market_slug)
        if action == "simulate":
            return await _handle_simulate(api_client, market_slug, query, amount, outcome)
        if action == "trending":
            return await _handle_trending(api_client, category)
        if action == "compare":
            return await _handle_compare(api_client, market_slugs)
        if action == "scenario":
            return await _handle_scenario(
                api_client, market_slug, query, allocation_mode,
                allocation_value, outcome, time_horizon, income_bracket,
            )
        return await _handle_browse(api_client, query=query, category=category)
    except Exception as exc:
        error_str = str(exc)
        if "timeout" in error_str.lower() or "timed out" in error_str.lower():
            return ToolResult.fail("POLYMARKET_TIMEOUT")
        return ToolResult.fail("POLYMARKET_API_ERROR", detail=error_str)


# ---------------------------------------------------------------------------
# Browse / Search
# ---------------------------------------------------------------------------


async def _handle_browse(
    api_client: Any,
    query: str | None = None,
    category: str | None = None,
) -> ToolResult:
    """Browse or search active prediction markets with enriched fields."""
    raw = await api_client.get_polymarket_markets(
        category=category,
        query=query,
    )

    markets = raw if isinstance(raw, list) else raw.get("markets", [])
    if not markets:
        return ToolResult.fail("NO_MARKETS_FOUND")

    formatted = [format_market_summary(m) for m in markets]

    return ToolResult.ok(
        {
            "markets": formatted,
            "total_markets": len(formatted),
            "action": "search" if query else "browse",
            "disclaimer": "Prediction market data sourced from Polymarket via Gamma API. Not financial advice.",
        },
        source="prediction_markets",
    )


# ---------------------------------------------------------------------------
# Analyze (enriched)
# ---------------------------------------------------------------------------


async def _handle_analyze(api_client: Any, market_slug: str) -> ToolResult:
    """Analyze a single prediction market with EV, Kelly, and efficiency metrics."""
    market = await api_client.get_polymarket_market(market_slug)

    if not market:
        return ToolResult.fail("MARKET_NOT_FOUND", slug=market_slug)

    summary = format_market_summary(market)

    # Enriched fields
    bid = float(market.get("bestBid") or 0)
    ask = float(market.get("bestAsk") or 0)
    volume = float(market.get("volume24hr") or 0)

    # Use first outcome (Yes) price for EV/Kelly
    yes_price = summary["outcomes"][0]["price"] if summary["outcomes"] else 0
    prob = max(0.001, min(0.999, yes_price))
    odds = (1.0 / prob - 1) if prob > 0 and prob < 1 else 0

    ev_result = expected_value(prob, 1.0, prob)
    kelly_result = kelly_fraction(prob, odds, 10000)  # Normalized to $10k bankroll
    efficiency = market_efficiency_score(bid, ask, volume) if bid > 0 and ask > 0 else {
        "spread": 0, "spread_pct": 0, "midpoint": 0,
        "liquidity_grade": "N/A", "efficiency_rating": "unknown",
    }

    return ToolResult.ok(
        {
            "question": summary["question"],
            "slug": summary["slug"],
            "description": market.get("description", ""),
            "outcomes": summary["outcomes"],
            "volume_24h": summary["volume_24h"],
            "category": summary["category"],
            "end_date": summary["end_date"],
            "active": summary["active"],
            "implied_probabilities": summary["implied_probabilities"],
            "best_bid": bid,
            "best_ask": ask,
            "ev_analysis": ev_result,
            "kelly_hint": kelly_result,
            "market_efficiency": efficiency,
            "action": "analyze",
            "disclaimer": "Prediction market data sourced from Polymarket via Gamma API. Not financial advice.",
        },
        source="prediction_markets",
    )


# ---------------------------------------------------------------------------
# Positions (enriched with P&L)
# ---------------------------------------------------------------------------


async def _handle_positions(api_client: Any) -> ToolResult:
    """List user's Polymarket positions with P&L and exposure metrics."""
    positions = await api_client.get_polymarket_positions()

    if not positions:
        return ToolResult.ok(
            {
                "positions": [],
                "total_positions": 0,
                "exposure_pct": 0.0,
                "action": "positions",
                "disclaimer": "No Polymarket positions found.",
            },
            source="prediction_markets",
        )

    # Get portfolio net worth for exposure calculation
    net_worth = 0.0
    try:
        details = await api_client.get_portfolio_details()
        summary = details.get("summary", {})
        net_worth = float(
            summary.get("currentValueInBaseCurrency", 0)
            or summary.get("currentNetWorth", 0)
        )
    except Exception:
        pass

    formatted: list[dict[str, Any]] = []
    total_position_value = 0.0
    for p in positions:
        current_price = float(p.get("outcomePrice", 0))
        entry_price = float(p.get("entryPrice", current_price))
        quantity = float(p.get("quantity", 0))
        unrealized_pnl = round((current_price - entry_price) * quantity, 2)
        unrealized_pnl_pct = round(
            ((current_price - entry_price) / entry_price) * 100, 2
        ) if entry_price > 0 else 0.0
        position_value = current_price * quantity
        total_position_value += position_value

        formatted.append({
            "id": p.get("id", ""),
            "slug": p.get("slug", ""),
            "question": p.get("question", ""),
            "outcome": p.get("outcome", ""),
            "entry_price": entry_price,
            "current_price": current_price,
            "quantity": quantity,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": unrealized_pnl_pct,
            "date": p.get("date", ""),
        })

    exposure = portfolio_exposure_pct(total_position_value, net_worth)

    return ToolResult.ok(
        {
            "positions": formatted,
            "total_positions": len(formatted),
            "exposure_pct": exposure,
            "action": "positions",
            "disclaimer": "Polymarket position data from your portfolio.",
        },
        source="prediction_markets",
    )


# ---------------------------------------------------------------------------
# Simulate
# ---------------------------------------------------------------------------


async def _handle_simulate(
    api_client: Any,
    market_slug: str | None,
    query: str | None,
    amount: float | None,
    outcome: str | None,
) -> ToolResult:
    """Simulate a single-bet what-if scenario."""
    # Validate amount
    if amount is None or amount <= 0:
        return ToolResult.fail("INVALID_SIMULATION_AMOUNT")

    # Resolve slug
    slug = market_slug
    if not slug and query:
        slug = await _resolve_slug(api_client, query)
    if not slug:
        return ToolResult.fail("MARKET_NOT_FOUND")

    market = await api_client.get_polymarket_market(slug)
    if not market:
        return ToolResult.fail("MARKET_NOT_FOUND", slug=slug)

    if not market.get("active", False):
        return ToolResult.fail("MARKET_INACTIVE")

    summary = format_market_summary(market)

    # Determine outcome side
    side = (outcome or "Yes").capitalize()
    if side not in ("Yes", "No"):
        side = "Yes"

    # Get price for chosen outcome
    outcome_idx = 0 if side == "Yes" else 1
    outcome_price = summary["outcomes"][outcome_idx]["price"] if outcome_idx < len(summary["outcomes"]) else 0
    if outcome_price <= 0:
        return ToolResult.fail("MARKET_NOT_FOUND")

    prob = max(0.001, min(0.999, outcome_price))
    odds = (1.0 / prob - 1) if prob > 0 and prob < 1 else 0

    shares = amount / outcome_price
    potential_profit = round(shares * 1.0 - amount, 2)
    potential_loss = round(-amount, 2)

    ev_result = expected_value(prob, 1.0, outcome_price)
    kelly_result = kelly_fraction(prob, odds, amount * 10)  # Use 10x amount as bankroll proxy

    # Portfolio concentration
    net_worth = 0.0
    try:
        details = await api_client.get_portfolio_details()
        port_summary = details.get("summary", {})
        net_worth = float(
            port_summary.get("currentValueInBaseCurrency", 0)
            or port_summary.get("currentNetWorth", 0)
        )
    except Exception:
        pass

    concentration_pct = portfolio_exposure_pct(amount, net_worth)
    r_level = risk_level(concentration_pct)

    return ToolResult.ok(
        {
            "market": {"question": summary["question"], "slug": summary["slug"]},
            "outcome": side,
            "amount": amount,
            "potential_profit": potential_profit,
            "potential_loss": potential_loss,
            "ev_analysis": ev_result,
            "kelly_hint": kelly_result,
            "portfolio_concentration_pct": concentration_pct,
            "risk_level": r_level,
            "action": "simulate",
            "disclaimer": "Hypothetical simulation for informational purposes only. Not financial advice.",
        },
        source="prediction_markets",
    )


# ---------------------------------------------------------------------------
# Trending
# ---------------------------------------------------------------------------


async def _handle_trending(api_client: Any, category: str | None) -> ToolResult:
    """Top markets by 24h volume."""
    raw = await api_client.get_polymarket_markets(category=category)
    markets = raw if isinstance(raw, list) else raw.get("markets", [])

    if not markets:
        return ToolResult.fail("NO_MARKETS_FOUND")

    # Sort by volume desc, take top 10
    sorted_markets = sorted(markets, key=lambda m: float(m.get("volume24hr", 0)), reverse=True)[:10]
    formatted = [format_market_summary(m) for m in sorted_markets]

    return ToolResult.ok(
        {
            "trending_markets": formatted,
            "total": len(formatted),
            "sort_by": "volume_24h",
            "action": "trending",
            "disclaimer": "Prediction market data sourced from Polymarket via Gamma API. Not financial advice.",
        },
        source="prediction_markets",
    )


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


async def _handle_compare(
    api_client: Any,
    market_slugs: list[str] | None,
) -> ToolResult:
    """Side-by-side comparison of 2-3 markets."""
    if not market_slugs or len(market_slugs) < 2 or len(market_slugs) > 3:
        return ToolResult.fail("INVALID_COMPARISON_COUNT")

    markets: list[dict[str, Any]] = []
    for slug in market_slugs:
        market = await api_client.get_polymarket_market(slug)
        if not market:
            return ToolResult.fail("MARKET_NOT_FOUND", slug=slug)
        summary = format_market_summary(market)

        # Add efficiency metrics
        bid = float(market.get("bestBid") or 0)
        ask = float(market.get("bestAsk") or 0)
        volume = float(market.get("volume24hr") or 0)
        if bid > 0 and ask > 0:
            eff = market_efficiency_score(bid, ask, volume)
            summary["market_efficiency"] = eff
        markets.append(summary)

    # Build comparison matrix
    spread_winner = min(markets, key=lambda m: m.get("market_efficiency", {}).get("spread_pct", 999))["slug"]
    volume_winner = max(markets, key=lambda m: m.get("volume_24h", 0))["slug"]
    efficiency_winner = min(
        markets,
        key=lambda m: {"A": 0, "B": 1, "C": 2, "D": 3, "F": 4, "N/A": 5}.get(
            m.get("market_efficiency", {}).get("liquidity_grade", "F"), 5
        ),
    )["slug"]

    return ToolResult.ok(
        {
            "markets": markets,
            "comparison_matrix": {
                "spread_winner": spread_winner,
                "volume_winner": volume_winner,
                "efficiency_winner": efficiency_winner,
            },
            "action": "compare",
            "disclaimer": "Prediction market data sourced from Polymarket via Gamma API. Not financial advice.",
        },
        source="prediction_markets",
    )


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------


async def _handle_scenario(
    api_client: Any,
    market_slug: str | None,
    query: str | None,
    allocation_mode: str | None,
    allocation_value: float | None,
    outcome: str | None,
    time_horizon: str | None,
    income_bracket: str | None,
) -> ToolResult:
    """Model a portfolio reallocation into a prediction market."""
    # Validate allocation mode
    valid_modes = {"fixed", "percent", "all_in"}
    if not allocation_mode or allocation_mode not in valid_modes:
        return ToolResult.fail("INVALID_ALLOCATION_MODE")

    # Validate allocation value
    if allocation_mode != "all_in":
        if allocation_value is None or allocation_value <= 0:
            return ToolResult.fail("INVALID_ALLOCATION_VALUE")

    # Validate time horizon
    valid_horizons = {"1m", "3m", "6m", "1y"}
    if time_horizon and time_horizon not in valid_horizons:
        return ToolResult.fail("UNSUPPORTED_HORIZON")

    # Resolve slug
    slug = market_slug
    if not slug and query:
        slug = await _resolve_slug(api_client, query)
    if not slug:
        return ToolResult.fail("MARKET_NOT_FOUND")

    # Fetch market
    market = await api_client.get_polymarket_market(slug)
    if not market:
        return ToolResult.fail("MARKET_NOT_FOUND", slug=slug)

    if not market.get("active", False):
        return ToolResult.fail("MARKET_INACTIVE")

    # Get outcome price
    summary = format_market_summary(market)
    side = (outcome or "Yes").capitalize()
    if side not in ("Yes", "No"):
        side = "Yes"
    outcome_idx = 0 if side == "Yes" else 1
    outcome_price = summary["outcomes"][outcome_idx]["price"] if outcome_idx < len(summary["outcomes"]) else 0

    if outcome_price <= 0:
        return ToolResult.fail("MARKET_NOT_FOUND")

    # Get portfolio data
    try:
        details = await api_client.get_portfolio_details()
        port_summary = details.get("summary", {})
        net_worth = float(
            port_summary.get("currentValueInBaseCurrency", 0)
            or port_summary.get("currentNetWorth", 0)
        )
    except Exception:
        net_worth = 0.0

    if net_worth <= 0:
        return ToolResult.fail("EMPTY_PORTFOLIO")

    # Get holdings
    try:
        holdings_response = await api_client.get_portfolio_holdings()
        holdings = holdings_response.get("holdings", [])
        if isinstance(holdings, dict):
            holdings = list(holdings.values())
    except Exception:
        holdings = []

    # Validate allocation value against portfolio
    resolved_bracket = income_bracket or "middle"
    alloc_val = allocation_value or 0
    if allocation_mode == "all_in":
        alloc_val = 100.0  # Treat as 100% internally, compute_scenario handles it
    elif allocation_mode == "percent":
        if alloc_val > 100:
            return ToolResult.fail("INVALID_ALLOCATION_VALUE")
    elif allocation_mode == "fixed":
        if alloc_val > net_worth:
            return ToolResult.fail("INVALID_ALLOCATION_VALUE")

    # Compute scenario
    result = compute_scenario(
        net_worth=net_worth,
        holdings=holdings,
        market=market,
        allocation_mode=allocation_mode,
        allocation_value=alloc_val,
        outcome_price=outcome_price,
        income_bracket=resolved_bracket,
    )

    # Override outcome side if user specified
    result["market"]["outcome_side"] = side

    return ToolResult.ok(result, source="prediction_markets")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _resolve_slug(api_client: Any, query: str) -> str | None:
    """Search markets and return the slug of the highest-volume match."""
    raw = await api_client.get_polymarket_markets(query=query)
    markets = raw if isinstance(raw, list) else raw.get("markets", [])
    if not markets:
        return None
    # Sort by volume, take top
    sorted_markets = sorted(markets, key=lambda m: float(m.get("volume24hr", 0)), reverse=True)
    return sorted_markets[0].get("slug")
