"""Prediction Markets tool — browse, search, and analyze Polymarket markets."""

from __future__ import annotations

import json
from typing import Any

from agent.tools.base import ToolResult


async def explore_prediction_markets(
    api_client: Any,
    action: str = "browse",
    query: str | None = None,
    category: str | None = None,
    market_slug: str | None = None,
) -> ToolResult:
    """Browse, search, or analyze Polymarket prediction markets.

    Args:
        api_client: Injected Ghostfolio/mock API client.
        action: One of "browse", "search", "analyze", "positions".
        query: Search query for filtering markets.
        category: Category filter (e.g. "Crypto", "Politics").
        market_slug: Specific market slug for analysis.

    Returns:
        ToolResult with market data or structured error.
    """
    try:
        if action == "positions":
            return await _handle_positions(api_client)
        if action == "analyze" and market_slug:
            return await _handle_analyze(api_client, market_slug)
        return await _handle_browse(api_client, query=query, category=category)
    except Exception as exc:
        error_str = str(exc)
        if "timeout" in error_str.lower() or "timed out" in error_str.lower():
            return ToolResult.fail("POLYMARKET_TIMEOUT")
        return ToolResult.fail("POLYMARKET_API_ERROR", detail=error_str)


async def _handle_browse(
    api_client: Any,
    query: str | None = None,
    category: str | None = None,
) -> ToolResult:
    """Browse or search active prediction markets."""
    raw = await api_client.get_polymarket_markets(
        category=category,
        query=query,
    )

    markets = raw if isinstance(raw, list) else raw.get("markets", [])
    if not markets:
        return ToolResult.fail("NO_MARKETS_FOUND")

    formatted: list[dict[str, Any]] = []
    for m in markets:
        prices = m.get("outcomePrices", "[]")
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except (json.JSONDecodeError, TypeError):
                prices = []

        outcomes = m.get("outcomes", [])
        outcome_display: list[dict[str, Any]] = []
        for i, outcome in enumerate(outcomes):
            price = prices[i] if i < len(prices) else None
            outcome_display.append({"label": outcome, "price": price})

        formatted.append({
            "question": m.get("question", "Unknown"),
            "slug": m.get("slug", ""),
            "outcomes": outcome_display,
            "volume_24h": m.get("volume24hr", 0),
            "category": m.get("category", ""),
            "end_date": m.get("endDate", ""),
            "active": m.get("active", False),
        })

    return ToolResult.ok(
        {
            "markets": formatted,
            "total_markets": len(formatted),
            "action": "search" if query else "browse",
            "disclaimer": "Prediction market data sourced from Polymarket via Gamma API. Not financial advice.",
        },
        source="prediction_markets",
    )


async def _handle_analyze(api_client: Any, market_slug: str) -> ToolResult:
    """Analyze a single prediction market in detail."""
    market = await api_client.get_polymarket_market(market_slug)

    if not market:
        return ToolResult.fail("MARKET_NOT_FOUND", slug=market_slug)

    prices = market.get("outcomePrices", "[]")
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except (json.JSONDecodeError, TypeError):
            prices = []

    outcomes = market.get("outcomes", [])
    outcome_display: list[dict[str, Any]] = []
    for i, outcome in enumerate(outcomes):
        price = prices[i] if i < len(prices) else None
        outcome_display.append({"label": outcome, "price": price})

    return ToolResult.ok(
        {
            "question": market.get("question", "Unknown"),
            "slug": market.get("slug", ""),
            "description": market.get("description", ""),
            "outcomes": outcome_display,
            "volume_24h": market.get("volume24hr", 0),
            "category": market.get("category", ""),
            "end_date": market.get("endDate", ""),
            "active": market.get("active", False),
            "last_trade_price": market.get("lastTradePrice"),
            "best_bid": market.get("bestBid"),
            "best_ask": market.get("bestAsk"),
            "action": "analyze",
            "disclaimer": "Prediction market data sourced from Polymarket via Gamma API. Not financial advice.",
        },
        source="prediction_markets",
    )


async def _handle_positions(api_client: Any) -> ToolResult:
    """List user's Polymarket positions."""
    positions = await api_client.get_polymarket_positions()

    if not positions:
        return ToolResult.ok(
            {
                "positions": [],
                "total_positions": 0,
                "action": "positions",
                "disclaimer": "No Polymarket positions found.",
            },
            source="prediction_markets",
        )

    formatted: list[dict[str, Any]] = []
    for p in positions:
        formatted.append({
            "id": p.get("id", ""),
            "slug": p.get("slug", ""),
            "question": p.get("question", ""),
            "outcome": p.get("outcome", ""),
            "price": p.get("outcomePrice", 0),
            "quantity": p.get("quantity", 0),
            "date": p.get("date", ""),
        })

    return ToolResult.ok(
        {
            "positions": formatted,
            "total_positions": len(formatted),
            "action": "positions",
            "disclaimer": "Polymarket position data from your portfolio.",
        },
        source="prediction_markets",
    )
