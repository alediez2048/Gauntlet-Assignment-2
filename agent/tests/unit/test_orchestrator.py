"""Unit tests for the orchestrator node and multi-step detection."""

from __future__ import annotations

from typing import Any

import pytest

from agent.graph.nodes import (
    _detect_multi_step,
    make_orchestrator_node,
    route_after_orchestrator,
)
from agent.tools.base import ToolResult


def _make_state(**overrides: Any) -> dict[str, Any]:
    """Build a minimal AgentState dict with sensible defaults."""
    state: dict[str, Any] = {
        "pending_action": "valid",
        "step_count": 0,
        "tool_plan": [],
        "retry_count": 0,
        "tool_call_history": [],
    }
    state.update(overrides)
    return state


# ---------- _detect_multi_step ----------

class TestDetectMultiStep:
    def test_health_check_triggers_three_tool_plan(self) -> None:
        plan = _detect_multi_step("Give me a full portfolio health check")
        assert plan is not None
        assert len(plan) == 3
        assert plan[0]["tool_name"] == "analyze_portfolio_performance"
        assert plan[1]["tool_name"] == "advise_asset_allocation"
        assert plan[2]["tool_name"] == "check_compliance"

    def test_full_analysis_triggers_same_as_health_check(self) -> None:
        plan = _detect_multi_step("I want a full analysis of my portfolio")
        assert plan is not None
        assert len(plan) == 3

    def test_complete_review_triggers_three_tool_plan(self) -> None:
        plan = _detect_multi_step("Give me a complete review of everything")
        assert plan is not None
        assert len(plan) == 3
        assert plan[0]["tool_name"] == "analyze_portfolio_performance"
        assert plan[1]["tool_name"] == "categorize_transactions"
        assert plan[2]["tool_name"] == "estimate_capital_gains_tax"

    def test_portfolio_overview_triggers_two_tool_plan(self) -> None:
        plan = _detect_multi_step("Show me a portfolio overview")
        assert plan is not None
        assert len(plan) == 2
        assert plan[0]["tool_name"] == "analyze_portfolio_performance"
        assert plan[1]["tool_name"] == "advise_asset_allocation"

    def test_tax_and_compliance_triggers_two_tool_plan(self) -> None:
        plan = _detect_multi_step("Run tax and compliance checks")
        assert plan is not None
        assert len(plan) == 2
        assert plan[0]["tool_name"] == "estimate_capital_gains_tax"
        assert plan[1]["tool_name"] == "check_compliance"

    def test_no_match_returns_none(self) -> None:
        plan = _detect_multi_step("How is my portfolio doing?")
        assert plan is None

    def test_case_insensitive(self) -> None:
        plan = _detect_multi_step("FULL ANALYSIS please")
        assert plan is not None


# ---------- Orchestrator node ----------

class TestOrchestratorNode:
    def test_single_step_success_routes_to_synthesizer(self) -> None:
        node = make_orchestrator_node()
        state = _make_state(pending_action="valid", tool_plan=[], step_count=0)
        result = node(state)
        assert result["step_count"] == 1
        assert result["pending_action"] == "valid"
        assert route_after_orchestrator(result) == "valid"

    def test_multi_step_success_routes_to_next_step(self) -> None:
        node = make_orchestrator_node()
        state = _make_state(
            pending_action="valid",
            step_count=0,
            tool_plan=[{"route": "allocation", "tool_name": "advise_asset_allocation", "tool_args": {}}],
        )
        result = node(state)
        assert result["step_count"] == 1
        assert result["pending_action"] == "next_step"
        assert route_after_orchestrator(result) == "next_step"

    def test_failure_first_attempt_routes_to_retry(self) -> None:
        node = make_orchestrator_node()
        state = _make_state(
            pending_action="invalid_or_error",
            retry_count=0,
            step_count=0,
        )
        result = node(state)
        assert result["retry_count"] == 1
        assert result["pending_action"] == "retry"
        assert route_after_orchestrator(result) == "retry"

    def test_failure_after_retry_with_plan_routes_to_next_step(self) -> None:
        node = make_orchestrator_node()
        state = _make_state(
            pending_action="invalid_or_error",
            retry_count=1,
            step_count=0,
            tool_plan=[{"route": "compliance", "tool_name": "check_compliance", "tool_args": {}}],
        )
        result = node(state)
        assert result["pending_action"] == "next_step"

    def test_failure_after_retry_no_plan_with_prior_success_routes_to_synthesizer(self) -> None:
        node = make_orchestrator_node()
        state = _make_state(
            pending_action="invalid_or_error",
            retry_count=1,
            step_count=0,
            tool_plan=[],
            tool_call_history=[
                {"tool_name": "analyze_portfolio_performance", "success": True, "data": {}},
                {"tool_name": "check_compliance", "success": False, "error": "API_ERROR"},
            ],
        )
        result = node(state)
        assert result["pending_action"] == "valid"

    def test_failure_after_retry_no_plan_all_failed_routes_to_error(self) -> None:
        node = make_orchestrator_node()
        state = _make_state(
            pending_action="invalid_or_error",
            retry_count=1,
            step_count=0,
            tool_plan=[],
            tool_call_history=[
                {"tool_name": "check_compliance", "success": False, "error": "API_ERROR"},
            ],
        )
        result = node(state)
        assert result["pending_action"] == "invalid_or_error"
        assert route_after_orchestrator(result) == "invalid_or_error"

    def test_max_steps_reached_routes_to_synthesizer(self) -> None:
        """Even if tool_plan has items, stop at _MAX_STEPS (3)."""
        node = make_orchestrator_node()
        state = _make_state(
            pending_action="valid",
            step_count=2,  # Will become 3 after increment
            tool_plan=[{"route": "tax", "tool_name": "estimate_capital_gains_tax", "tool_args": {}}],
        )
        result = node(state)
        assert result["step_count"] == 3
        assert result["pending_action"] == "valid"


# ---------- route_after_orchestrator ----------

class TestRouteAfterOrchestrator:
    def test_valid(self) -> None:
        assert route_after_orchestrator({"pending_action": "valid"}) == "valid"

    def test_next_step(self) -> None:
        assert route_after_orchestrator({"pending_action": "next_step"}) == "next_step"

    def test_retry(self) -> None:
        assert route_after_orchestrator({"pending_action": "retry"}) == "retry"

    def test_error(self) -> None:
        assert route_after_orchestrator({"pending_action": "invalid_or_error"}) == "invalid_or_error"

    def test_unknown_defaults_to_error(self) -> None:
        assert route_after_orchestrator({"pending_action": "something_else"}) == "invalid_or_error"
