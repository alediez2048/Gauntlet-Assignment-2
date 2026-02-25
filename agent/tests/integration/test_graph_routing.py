from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from agent.clients.mock_client import MockGhostfolioClient
from agent.graph.graph import build_graph
from agent.graph import nodes as graph_nodes
from agent.tools.base import ToolResult

RouterFn = Callable[[str, list[Any]], Awaitable[dict[str, Any]]]


def _router_with(decision: dict[str, Any]) -> RouterFn:
    async def _router(user_query: str, messages: list[Any]) -> dict[str, Any]:
        del user_query
        del messages
        return decision

    return _router


async def _run_graph(
    *,
    mock_ghostfolio_client: MockGhostfolioClient,
    route: str,
    tool_name: str | None,
    tool_args: dict[str, Any],
    query: str,
) -> dict[str, Any]:
    graph = build_graph(
        api_client=mock_ghostfolio_client,
        router=_router_with(
            {
                "route": route,
                "tool_name": tool_name,
                "tool_args": tool_args,
                "reason": "test_route",
            }
        ),
    )
    return await graph.ainvoke(
        {
            "messages": [{"role": "user", "content": query}],
            "tool_call_history": [],
        }
    )


@pytest.mark.asyncio
async def test_graph_routes_portfolio_query_to_performance_tool(
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    result = await _run_graph(
        mock_ghostfolio_client=mock_ghostfolio_client,
        route="portfolio",
        tool_name="analyze_portfolio_performance",
        tool_args={"time_period": "ytd"},
        query="How is my portfolio doing this year?",
    )

    assert result["route"] == "portfolio"
    assert result["tool_name"] == "analyze_portfolio_performance"
    assert result["pending_action"] == "valid"
    assert result["error"] is None
    assert len(result["tool_call_history"]) == 1
    assert result["tool_call_history"][0]["tool_name"] == "analyze_portfolio_performance"
    assert result["tool_call_history"][0]["success"] is True
    assert result["final_response"]["category"] == "analysis"


@pytest.mark.asyncio
async def test_graph_routes_transactions_query_to_transaction_tool(
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    result = await _run_graph(
        mock_ghostfolio_client=mock_ghostfolio_client,
        route="transactions",
        tool_name="categorize_transactions",
        tool_args={"date_range": "max"},
        query="Categorize my recent transactions.",
    )

    assert result["route"] == "transactions"
    assert result["tool_name"] == "categorize_transactions"
    assert result["pending_action"] == "valid"
    assert result["error"] is None
    assert len(result["tool_call_history"]) == 1
    assert result["tool_call_history"][0]["tool_name"] == "categorize_transactions"
    assert result["tool_call_history"][0]["success"] is True
    assert result["final_response"]["category"] == "analysis"


@pytest.mark.asyncio
async def test_graph_routes_tax_query_to_tax_tool(
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    result = await _run_graph(
        mock_ghostfolio_client=mock_ghostfolio_client,
        route="tax",
        tool_name="estimate_capital_gains_tax",
        tool_args={"tax_year": 2025, "income_bracket": "middle"},
        query="Estimate my tax implications for 2025.",
    )

    assert result["route"] == "tax"
    assert result["tool_name"] == "estimate_capital_gains_tax"
    assert result["pending_action"] == "valid"
    assert result["error"] is None
    assert len(result["tool_call_history"]) == 1
    assert result["tool_call_history"][0]["tool_name"] == "estimate_capital_gains_tax"
    assert result["tool_call_history"][0]["success"] is True
    assert result["final_response"]["category"] == "analysis"


@pytest.mark.asyncio
async def test_graph_routes_allocation_query_to_allocation_tool(
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    result = await _run_graph(
        mock_ghostfolio_client=mock_ghostfolio_client,
        route="allocation",
        tool_name="advise_asset_allocation",
        tool_args={"target_profile": "balanced"},
        query="Am I diversified enough?",
    )

    assert result["route"] == "allocation"
    assert result["tool_name"] == "advise_asset_allocation"
    assert result["pending_action"] == "valid"
    assert result["error"] is None
    assert len(result["tool_call_history"]) == 1
    assert result["tool_call_history"][0]["tool_name"] == "advise_asset_allocation"
    assert result["tool_call_history"][0]["success"] is True
    assert result["final_response"]["category"] == "analysis"


@pytest.mark.asyncio
async def test_graph_routes_ambiguous_query_to_clarifier(
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    result = await _run_graph(
        mock_ghostfolio_client=mock_ghostfolio_client,
        route="clarify",
        tool_name=None,
        tool_args={},
        query="What's the weather today?",
    )

    assert result["route"] == "clarify"
    assert result["tool_name"] is None
    assert result["pending_action"] == "ambiguous_or_unsupported"
    assert result.get("tool_call_history", []) == []
    assert result["final_response"]["category"] == "clarification"


@pytest.mark.asyncio
async def test_graph_routes_failed_tool_result_to_error_handler(
    monkeypatch: pytest.MonkeyPatch,
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    original_tool = graph_nodes._TOOL_FUNCTIONS["analyze_portfolio_performance"]

    async def _failing_tool(api_client: Any, time_period: str = "ytd") -> ToolResult:
        del api_client
        del time_period
        return ToolResult.fail("API_TIMEOUT")

    monkeypatch.setitem(
        graph_nodes._TOOL_FUNCTIONS,
        "analyze_portfolio_performance",
        _failing_tool,
    )

    try:
        result = await _run_graph(
            mock_ghostfolio_client=mock_ghostfolio_client,
            route="portfolio",
            tool_name="analyze_portfolio_performance",
            tool_args={"time_period": "ytd"},
            query="How is my portfolio doing this year?",
        )
    finally:
        monkeypatch.setitem(
            graph_nodes._TOOL_FUNCTIONS,
            "analyze_portfolio_performance",
            original_tool,
        )

    assert result["route"] == "portfolio"
    assert result["tool_name"] == "analyze_portfolio_performance"
    assert result["pending_action"] == "invalid_or_error"
    assert result["error"] == "API_TIMEOUT"
    assert len(result["tool_call_history"]) == 1
    assert result["tool_call_history"][0]["success"] is False
    assert result["tool_call_history"][0]["error"] == "API_TIMEOUT"
    assert result["final_response"]["category"] == "error"
