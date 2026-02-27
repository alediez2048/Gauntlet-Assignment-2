"""Typed state definitions for the LangGraph orchestration flow."""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

try:
    from langgraph.graph import add_messages
except ModuleNotFoundError:
    def add_messages(existing: list[Any], new_messages: list[Any]) -> list[Any]:
        """Fallback reducer when LangGraph is not installed."""
        return [*(existing or []), *(new_messages or [])]

from agent.tools.base import ToolResult

RouteName = Literal["portfolio", "transactions", "tax", "allocation", "compliance", "market", "clarify"]
ToolName = Literal[
    "analyze_portfolio_performance",
    "categorize_transactions",
    "estimate_capital_gains_tax",
    "advise_asset_allocation",
    "check_compliance",
    "get_market_data",
]
PendingAction = Literal["tool_selected", "ambiguous_or_unsupported", "valid", "invalid_or_error"]


class ToolCallRecord(TypedDict, total=False):
    """Tracks one executed tool invocation for observability/SSE."""

    route: RouteName
    tool_name: ToolName
    tool_args: dict[str, Any]
    success: bool
    error: str | None
    data: dict[str, Any] | None


class FinalResponse(TypedDict, total=False):
    """Normalized response payload used by end nodes."""

    category: Literal["analysis", "clarification", "error"]
    message: str
    tool_name: ToolName | None
    data: dict[str, Any] | None
    suggestions: list[str]


class AgentState(TypedDict, total=False):
    """State contract for Router -> ToolExecutor -> Validator -> Orchestrator -> terminal nodes."""

    messages: Annotated[list[Any], add_messages]
    portfolio_snapshot: dict[str, Any]
    pending_action: PendingAction
    route: RouteName
    tool_name: ToolName | None
    tool_args: dict[str, Any]
    tool_result: ToolResult | None
    tool_call_history: list[ToolCallRecord]
    error: str | None
    final_response: FinalResponse
    reasoning: str | None
    step_count: int
    tool_plan: list[dict[str, Any]]
    retry_count: int
