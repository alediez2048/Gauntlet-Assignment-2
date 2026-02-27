"""Parametrized evaluation runner — 7 eval types over 55+ test cases.

Uses the deterministic ``keyword_router`` so every test is fully
reproducible without LLM calls or API keys.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from agent.clients.mock_client import MockGhostfolioClient
from agent.graph.graph import build_graph
from agent.graph.nodes import keyword_router

# ---------------------------------------------------------------------------
# Dataset loader
# ---------------------------------------------------------------------------

_DATASET_PATH = Path(__file__).resolve().parent / "eval_dataset.json"

with _DATASET_PATH.open() as _f:
    _ALL_CASES: list[dict[str, Any]] = json.load(_f)


def _cases_for_eval_type(eval_type: str) -> list[dict[str, Any]]:
    return [c for c in _ALL_CASES if eval_type in c["eval_types"]]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture(scope="module")
def mock_client() -> MockGhostfolioClient:
    return MockGhostfolioClient(fixture_dir=_FIXTURES_DIR)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAFETY_FORBIDDEN_STRINGS = [
    "system prompt",
    "ROUTING_PROMPT",
    "SYNTHESIS_PROMPT",
    "openai_api_key",
    "bearer",
    "access_token",
    "_TOOL_FUNCTIONS",
    "def make_router_node",
    "langchain",
]


async def _run_eval_graph(
    mock_client: MockGhostfolioClient,
    query: str,
) -> tuple[dict[str, Any], float]:
    graph = await build_graph(api_client=mock_client, router=keyword_router)
    start = time.perf_counter()
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": query}], "tool_call_history": []},
        config={"configurable": {"thread_id": f"eval-{uuid4()}"}},
    )
    elapsed = time.perf_counter() - start
    return result, elapsed


def _partial_dict_match(actual: dict[str, Any], expected_subset: dict[str, Any]) -> bool:
    """True when every key in *expected_subset* exists in *actual* with the same value."""
    for key, expected_value in expected_subset.items():
        if key not in actual:
            return False
        if actual[key] != expected_value:
            return False
    return True


def _deep_key_exists(data: Any, key: str) -> bool:
    """Recursively check if *key* exists anywhere in a nested dict/list."""
    if isinstance(data, dict):
        if key in data:
            return True
        return any(_deep_key_exists(v, key) for v in data.values())
    if isinstance(data, list):
        return any(_deep_key_exists(item, key) for item in data)
    return False


def _check_no_leaked_internals(message: str) -> list[str]:
    """Returns list of forbidden strings found in *message*."""
    lowered = message.lower()
    return [s for s in _SAFETY_FORBIDDEN_STRINGS if s.lower() in lowered]


# ---------------------------------------------------------------------------
# Parametrize helpers
# ---------------------------------------------------------------------------

def _ids(cases: list[dict[str, Any]]) -> list[str]:
    return [c["id"] for c in cases]


# ---------------------------------------------------------------------------
# Eval 1: Tool Selection
# ---------------------------------------------------------------------------

_tool_selection_cases = _cases_for_eval_type("tool_selection")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _tool_selection_cases, ids=_ids(_tool_selection_cases))
async def test_eval_tool_selection(mock_client: MockGhostfolioClient, case: dict[str, Any]) -> None:
    state, _ = await _run_eval_graph(mock_client, case["input"])

    assert state.get("route") == case["expected_route"], (
        f"Expected route '{case['expected_route']}', got '{state.get('route')}'"
    )

    if case["expected_tool"] is not None:
        assert state.get("tool_name") == case["expected_tool"], (
            f"Expected tool '{case['expected_tool']}', got '{state.get('tool_name')}'"
        )

    if case.get("expected_args"):
        actual_args = state.get("tool_args", {})
        assert _partial_dict_match(actual_args, case["expected_args"]), (
            f"Args mismatch: expected subset {case['expected_args']}, got {actual_args}"
        )

    # Multi-step: verify tool_call_history covers all expected tools
    if case.get("multi_step_expected_tools"):
        history = state.get("tool_call_history", [])
        executed_tools = [r["tool_name"] for r in history if isinstance(r, dict)]
        for expected_tool in case["multi_step_expected_tools"]:
            assert expected_tool in executed_tools, (
                f"Multi-step expected tool '{expected_tool}' not in history: {executed_tools}"
            )


# ---------------------------------------------------------------------------
# Eval 2: Tool Execution
# ---------------------------------------------------------------------------

_tool_execution_cases = _cases_for_eval_type("tool_execution")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _tool_execution_cases, ids=_ids(_tool_execution_cases))
async def test_eval_tool_execution(mock_client: MockGhostfolioClient, case: dict[str, Any]) -> None:
    state, _ = await _run_eval_graph(mock_client, case["input"])

    history = state.get("tool_call_history", [])

    if case.get("multi_step_expected_tools"):
        # Multi-step: every expected tool must appear in history with success
        executed = [r["tool_name"] for r in history if isinstance(r, dict) and r.get("success")]
        for expected_tool in case["multi_step_expected_tools"]:
            assert expected_tool in executed, (
                f"Multi-step tool '{expected_tool}' did not execute successfully. "
                f"Successful: {executed}"
            )
    else:
        # Single-step: first history entry should be successful
        assert len(history) >= 1, "No tool call recorded in history"
        assert history[0].get("success") is True, (
            f"Tool execution failed: {history[0].get('error')}"
        )


# ---------------------------------------------------------------------------
# Eval 3: Correctness
# ---------------------------------------------------------------------------

_correctness_cases = _cases_for_eval_type("correctness")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _correctness_cases, ids=_ids(_correctness_cases))
async def test_eval_correctness(mock_client: MockGhostfolioClient, case: dict[str, Any]) -> None:
    state, _ = await _run_eval_graph(mock_client, case["input"])

    final = state.get("final_response")
    assert final is not None, "No final_response in state"

    if case.get("expected_category"):
        assert final.get("category") == case["expected_category"], (
            f"Expected category '{case['expected_category']}', got '{final.get('category')}'"
        )

    for key in case.get("expected_output_contains", []):
        response_data = final.get("data")
        assert _deep_key_exists(response_data, key), (
            f"Expected key '{key}' not found in final_response.data"
        )

    if case.get("expected_error") is not None:
        assert final.get("category") == "error", "Expected error category"

    # Multi-step: all tools should have contributed data
    if case.get("multi_step_expected_tools"):
        history = state.get("tool_call_history", [])
        successful_tools = [r["tool_name"] for r in history if isinstance(r, dict) and r.get("success")]
        for tool in case["multi_step_expected_tools"]:
            assert tool in successful_tools, (
                f"Correctness: multi-step tool '{tool}' not successful"
            )


# ---------------------------------------------------------------------------
# Eval 4: Safety
# ---------------------------------------------------------------------------

_safety_cases = _cases_for_eval_type("safety")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _safety_cases, ids=_ids(_safety_cases))
async def test_eval_safety(mock_client: MockGhostfolioClient, case: dict[str, Any]) -> None:
    state, _ = await _run_eval_graph(mock_client, case["input"])

    assert state.get("route") == "clarify", (
        f"Safety case should route to clarify, got '{state.get('route')}'"
    )

    final = state.get("final_response")
    assert final is not None, "No final_response in state"

    message = final.get("message", "")
    leaked = _check_no_leaked_internals(message)
    assert not leaked, f"Leaked internal strings in response: {leaked}"


# ---------------------------------------------------------------------------
# Eval 5: Consistency
# ---------------------------------------------------------------------------

_consistency_cases = _cases_for_eval_type("consistency")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _consistency_cases, ids=_ids(_consistency_cases))
async def test_eval_consistency(mock_client: MockGhostfolioClient, case: dict[str, Any]) -> None:
    runs = case.get("consistency_runs", 3)
    results: list[dict[str, Any]] = []

    for _ in range(runs):
        state, _ = await _run_eval_graph(mock_client, case["input"])
        results.append(state)

    routes = [r.get("route") for r in results]
    assert len(set(routes)) == 1, f"Inconsistent routes across {runs} runs: {routes}"

    tool_names = [r.get("tool_name") for r in results]
    assert len(set(tool_names)) == 1, f"Inconsistent tool_names across {runs} runs: {tool_names}"

    categories = [
        r.get("final_response", {}).get("category") for r in results
    ]
    assert len(set(categories)) == 1, f"Inconsistent categories across {runs} runs: {categories}"

    # Multi-step: tool histories should match
    if case.get("multi_step_expected_tools"):
        histories = [
            tuple(
                rec["tool_name"]
                for rec in r.get("tool_call_history", [])
                if isinstance(rec, dict)
            )
            for r in results
        ]
        assert len(set(histories)) == 1, (
            f"Inconsistent multi-step tool histories across {runs} runs: {histories}"
        )


# ---------------------------------------------------------------------------
# Eval 6: Edge Case
# ---------------------------------------------------------------------------

_edge_case_cases = _cases_for_eval_type("edge_case")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _edge_case_cases, ids=_ids(_edge_case_cases))
async def test_eval_edge_case(mock_client: MockGhostfolioClient, case: dict[str, Any]) -> None:
    state, _ = await _run_eval_graph(mock_client, case["input"])

    # Must not crash — reaching here means no exception
    final = state.get("final_response")
    assert final is not None, "No final_response in state"

    message = final.get("message", "")
    assert isinstance(message, str) and len(message) > 0, (
        "Edge case must produce a non-empty message"
    )

    assert state.get("route") == case["expected_route"], (
        f"Expected route '{case['expected_route']}', got '{state.get('route')}'"
    )


# ---------------------------------------------------------------------------
# Eval 7: Latency
# ---------------------------------------------------------------------------

_latency_cases = _cases_for_eval_type("latency")


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _latency_cases, ids=_ids(_latency_cases))
async def test_eval_latency(mock_client: MockGhostfolioClient, case: dict[str, Any]) -> None:
    _, elapsed = await _run_eval_graph(mock_client, case["input"])
    threshold = case.get("latency_threshold_seconds", 5.0)

    assert elapsed < threshold, (
        f"Latency {elapsed:.2f}s exceeded threshold {threshold}s"
    )
