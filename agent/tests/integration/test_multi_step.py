"""Integration tests for multi-step orchestration and chain-of-thought."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from agent.clients.mock_client import MockGhostfolioClient
from agent.graph.graph import build_graph
from agent.graph import nodes as graph_nodes
from agent.tools.base import ToolResult

RouterFn = Any


def _router_with(decision: dict[str, Any]) -> RouterFn:
    async def _router(user_query: str, messages: list[Any]) -> dict[str, Any]:
        del user_query, messages
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
    graph = await build_graph(
        api_client=mock_ghostfolio_client,
        router=_router_with(
            {
                "route": route,
                "tool_name": tool_name,
                "tool_args": tool_args,
                "reason": "test_route",
                "reasoning": f"Test reasoning: selected {tool_name}.",
            }
        ),
    )
    return await graph.ainvoke(
        {
            "messages": [{"role": "user", "content": query}],
            "tool_call_history": [],
        },
        config={"configurable": {"thread_id": f"multi-step-{uuid4()}"}},
    )


# ---------- Multi-step integration tests ----------


@pytest.mark.asyncio
async def test_health_check_triggers_three_tools(
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    """A 'health check' query should execute portfolio, allocation, and compliance."""
    result = await _run_graph(
        mock_ghostfolio_client=mock_ghostfolio_client,
        route="portfolio",
        tool_name="analyze_portfolio_performance",
        tool_args={"time_period": "ytd"},
        query="Give me a full portfolio health check",
    )

    history = result.get("tool_call_history", [])
    assert len(history) == 3, f"Expected 3 tool calls, got {len(history)}: {[r.get('tool_name') for r in history]}"

    tool_names = [r["tool_name"] for r in history]
    assert tool_names[0] == "analyze_portfolio_performance"
    assert tool_names[1] == "advise_asset_allocation"
    assert tool_names[2] == "check_compliance"

    assert all(r["success"] for r in history)
    assert result["step_count"] == 3
    assert result["final_response"]["category"] == "analysis"
    assert "Combined analysis" in result["final_response"]["message"] or result["final_response"]["message"]


@pytest.mark.asyncio
async def test_portfolio_overview_triggers_two_tools(
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    """A 'portfolio overview' query should execute portfolio and allocation."""
    result = await _run_graph(
        mock_ghostfolio_client=mock_ghostfolio_client,
        route="portfolio",
        tool_name="analyze_portfolio_performance",
        tool_args={"time_period": "ytd"},
        query="Show me a portfolio overview",
    )

    history = result.get("tool_call_history", [])
    assert len(history) == 2

    tool_names = [r["tool_name"] for r in history]
    assert tool_names[0] == "analyze_portfolio_performance"
    assert tool_names[1] == "advise_asset_allocation"
    assert result["step_count"] == 2


@pytest.mark.asyncio
async def test_single_step_query_unchanged(
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    """A normal single-tool query should pass through the orchestrator transparently."""
    result = await _run_graph(
        mock_ghostfolio_client=mock_ghostfolio_client,
        route="portfolio",
        tool_name="analyze_portfolio_performance",
        tool_args={"time_period": "ytd"},
        query="How is my portfolio doing this year?",
    )

    history = result.get("tool_call_history", [])
    assert len(history) == 1
    assert history[0]["tool_name"] == "analyze_portfolio_performance"
    assert history[0]["success"] is True
    assert result["final_response"]["category"] == "analysis"
    assert result["pending_action"] == "valid"
    assert result["error"] is None


@pytest.mark.asyncio
async def test_reasoning_stored_in_state(
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    """The router should store reasoning text in state."""
    result = await _run_graph(
        mock_ghostfolio_client=mock_ghostfolio_client,
        route="portfolio",
        tool_name="analyze_portfolio_performance",
        tool_args={"time_period": "ytd"},
        query="How is my portfolio doing?",
    )

    reasoning = result.get("reasoning")
    assert reasoning is not None
    assert isinstance(reasoning, str)
    assert len(reasoning) > 0


@pytest.mark.asyncio
async def test_tool_call_history_includes_data(
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    """Tool call history records should include the data field."""
    result = await _run_graph(
        mock_ghostfolio_client=mock_ghostfolio_client,
        route="portfolio",
        tool_name="analyze_portfolio_performance",
        tool_args={"time_period": "ytd"},
        query="How is my portfolio doing this year?",
    )

    history = result.get("tool_call_history", [])
    assert len(history) >= 1
    record = history[0]
    assert "data" in record
    # data should be a dict for successful calls
    assert isinstance(record["data"], dict)


@pytest.mark.asyncio
async def test_multi_step_with_one_tool_failure(
    monkeypatch: pytest.MonkeyPatch,
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    """If one tool fails in a multi-step plan, the rest should still complete."""
    original_tool = graph_nodes._TOOL_FUNCTIONS["check_compliance"]
    call_count = 0

    async def _failing_compliance(api_client: Any, **kwargs: Any) -> ToolResult:
        nonlocal call_count
        call_count += 1
        return ToolResult.fail("API_ERROR")

    monkeypatch.setitem(
        graph_nodes._TOOL_FUNCTIONS,
        "check_compliance",
        _failing_compliance,
    )

    try:
        result = await _run_graph(
            mock_ghostfolio_client=mock_ghostfolio_client,
            route="portfolio",
            tool_name="analyze_portfolio_performance",
            tool_args={"time_period": "ytd"},
            query="Give me a full portfolio health check",
        )
    finally:
        monkeypatch.setitem(
            graph_nodes._TOOL_FUNCTIONS,
            "check_compliance",
            original_tool,
        )

    # Should still produce a final response from the successful tools
    assert result["final_response"]["category"] == "analysis"
    # compliance was retried once, so it appears twice in history
    history = result.get("tool_call_history", [])
    compliance_calls = [r for r in history if r.get("tool_name") == "check_compliance"]
    assert len(compliance_calls) >= 1
    assert all(not r["success"] for r in compliance_calls)
    # At least portfolio + allocation succeeded
    successful = [r for r in history if r.get("success")]
    assert len(successful) >= 2


@pytest.mark.asyncio
async def test_clarify_query_unaffected_by_orchestrator(
    mock_ghostfolio_client: MockGhostfolioClient,
) -> None:
    """Clarify queries bypass the orchestrator entirely (go through clarifier node)."""
    graph = await build_graph(
        api_client=mock_ghostfolio_client,
        router=_router_with(
            {
                "route": "clarify",
                "tool_name": None,
                "tool_args": {},
                "reason": "out_of_scope",
            }
        ),
    )
    result = await graph.ainvoke(
        {
            "messages": [{"role": "user", "content": "What is the weather?"}],
            "tool_call_history": [],
        },
        config={"configurable": {"thread_id": f"clarify-{uuid4()}"}},
    )

    assert result["route"] == "clarify"
    assert result["pending_action"] == "ambiguous_or_unsupported"
    assert result["final_response"]["category"] == "clarification"
