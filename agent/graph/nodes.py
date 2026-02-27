"""Node implementations for the LangGraph 6-node topology."""

from __future__ import annotations

import json
import math
import re
import traceback as _tb
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast

from agent.clients.ghostfolio_client import VALID_DATE_RANGES
from agent.graph.state import AgentState, RouteName, ToolName
from agent.prompts import SUPPORTED_CAPABILITIES, SYNTHESIS_PROMPT
from agent.tools.allocation_advisor import advise_asset_allocation
from agent.tools.base import ToolResult
from agent.tools.compliance_checker import check_compliance
from agent.tools.market_data import get_market_data
from agent.tools.portfolio_analyzer import analyze_portfolio_performance
from agent.tools.tax_estimator import estimate_capital_gains_tax
from agent.tools.transaction_categorizer import categorize_transactions

try:
    from langchain_core.messages import AIMessage as _AIMessage  # type: ignore[import-not-found]
except ModuleNotFoundError:
    _AIMessage = None

RouterCallable = Callable[[str, list[Any]], Awaitable[dict[str, Any]]]

_ROUTE_TO_TOOL: Final[dict[str, ToolName]] = {
    "portfolio": "analyze_portfolio_performance",
    "transactions": "categorize_transactions",
    "tax": "estimate_capital_gains_tax",
    "allocation": "advise_asset_allocation",
    "compliance": "check_compliance",
    "market": "get_market_data",
}
_VALID_ROUTES: Final[set[RouteName]] = {
    "portfolio",
    "transactions",
    "tax",
    "allocation",
    "compliance",
    "market",
    "clarify",
}
_TOOL_FUNCTIONS: Final[dict[ToolName, Callable[..., Awaitable[ToolResult]]]] = {
    "analyze_portfolio_performance": analyze_portfolio_performance,
    "categorize_transactions": categorize_transactions,
    "estimate_capital_gains_tax": estimate_capital_gains_tax,
    "advise_asset_allocation": advise_asset_allocation,
    "check_compliance": check_compliance,
    "get_market_data": get_market_data,
}
_VALID_INCOME_BRACKETS: Final[set[str]] = {"low", "middle", "high"}
_VALID_TARGET_PROFILES: Final[set[str]] = {"conservative", "balanced", "aggressive"}
_VALID_CHECK_TYPES: Final[set[str]] = {"all", "wash_sale", "pattern_day_trading", "concentration"}
_VALID_MARKET_METRICS: Final[set[str]] = {"price", "change", "change_percent", "currency", "market_value", "quantity", "all"}
_ROUTER_INTENTS: Final[dict[RouteName, tuple[str, ...]]] = {
    "portfolio": (
        "portfolio",
        "performance",
        "return",
        "gain",
        "loss",
        "how am i doing",
    ),
    "transactions": (
        "transaction",
        "activity",
        "activities",
        "bought",
        "sold",
        "dividend",
        "fee",
        "interest",
        "order",
    ),
    "tax": (
        "tax",
        "capital gains",
        "liability",
        "short term",
        "long term",
    ),
    "allocation": (
        "allocation",
        "diversification",
        "diversified",
        "rebalancing",
        "re-balance",
        "overweight",
        "underweight",
    ),
    "compliance": (
        "compliance",
        "wash sale",
        "pattern day trad",
        "regulation",
        "violation",
        "day trade",
        "day trading",
    ),
    "market": (
        "market data",
        "current price",
        "stock price",
        "market value",
        "price of",
        "prices",
        "quote",
        "what is .* trading at",
    ),
    "clarify": (),
}
_PROMPT_INJECTION_MARKERS: Final[tuple[str, ...]] = (
    "ignore previous instructions",
    "ignore your instructions",
    "system prompt",
    "developer message",
    "reveal prompt",
    "show hidden instructions",
)
_FOLLOW_UP_MARKERS: Final[tuple[str, ...]] = (
    "based on that",
    "based on this",
    "from that",
    "following up",
    "given that",
    "what should i do next",
)


SynthesizerCallable = Callable[[str, str], Awaitable[str]]


@dataclass(frozen=True)
class NodeDependencies:
    """Injected dependencies for graph nodes."""

    api_client: Any
    router: RouterCallable
    synthesizer: SynthesizerCallable | None = None


def _message_to_text(message: Any) -> str:
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
        return str(content)

    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content

    return str(content)


def _is_human_message(message: Any) -> bool:
    if isinstance(message, dict):
        role = str(message.get("role", "")).lower()
        return role in {"human", "user"}

    role = str(getattr(message, "role", "")).lower()
    if role in {"human", "user"}:
        return True

    message_type = str(getattr(message, "type", "")).lower()
    if message_type in {"human", "user"}:
        return True

    return message.__class__.__name__ == "HumanMessage"


def _assistant_message(content: str) -> Any:
    if _AIMessage is not None:
        return _AIMessage(content=content)

    return {"role": "assistant", "content": content}


def _latest_user_query(messages: list[Any]) -> str:
    for message in reversed(messages):
        if _is_human_message(message):
            return _message_to_text(message).strip()

    if messages:
        return _message_to_text(messages[-1]).strip()

    return ""


def _extract_date_range(query: str, default_value: str) -> str:
    lowered_query = query.lower()
    explicit_match = re.search(r"\b(1d|wtd|mtd|ytd|1y|5y|max)\b", lowered_query)
    if explicit_match is not None:
        return explicit_match.group(1)

    if "year to date" in lowered_query:
        return "ytd"
    if "today" in lowered_query or "daily" in lowered_query:
        return "1d"
    if "week" in lowered_query:
        return "wtd"
    if "month" in lowered_query:
        return "mtd"
    if "1 year" in lowered_query or "last year" in lowered_query:
        return "1y"
    if "5 year" in lowered_query or "five year" in lowered_query:
        return "5y"
    if "all time" in lowered_query or "inception" in lowered_query:
        return "max"

    return default_value


def _extract_tax_year(query: str, default_value: int) -> int:
    year_match = re.search(r"\b(20\d{2})\b", query)
    if year_match is None:
        return default_value

    try:
        return int(year_match.group(1))
    except ValueError:
        return default_value


def _extract_income_bracket(query: str, default_value: str) -> str:
    lowered_query = query.lower()
    if "low" in lowered_query:
        return "low"
    if "high" in lowered_query:
        return "high"
    if "middle" in lowered_query or "mid" in lowered_query:
        return "middle"

    return default_value


def _extract_target_profile(query: str, default_value: str) -> str:
    lowered_query = query.lower()
    if "conservative" in lowered_query:
        return "conservative"
    if "aggressive" in lowered_query:
        return "aggressive"
    if "balanced" in lowered_query:
        return "balanced"

    return default_value


def _extract_check_type(query: str, default_value: str) -> str:
    lowered_query = query.lower()
    if "wash sale" in lowered_query:
        return "wash_sale"
    if "pattern day trad" in lowered_query or "day trade" in lowered_query or "day trading" in lowered_query:
        return "pattern_day_trading"
    if "concentration" in lowered_query or "concentrated" in lowered_query:
        return "concentration"
    return default_value


def _extract_symbols(query: str) -> list[str] | None:
    """Extract stock ticker symbols from the query (e.g. SPY, AAPL)."""
    tickers = re.findall(r"\b[A-Z]{1,5}\b", query)
    # Filter out common English words that look like tickers
    stop_words = {"I", "A", "AM", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE",
                  "IF", "IN", "IS", "IT", "ME", "MY", "NO", "OF", "OK", "ON", "OR",
                  "SO", "TO", "UP", "US", "WE", "THE", "AND", "FOR", "ARE", "BUT",
                  "NOT", "YOU", "ALL", "ANY", "CAN", "HAS", "HER", "WAS", "ONE",
                  "OUR", "OUT", "HOW", "WHAT", "WITH", "SHOW", "GET", "MUCH"}
    filtered = [t for t in tickers if t not in stop_words]
    return filtered if filtered else None


def _default_args_for_tool(tool_name: ToolName, user_query: str) -> dict[str, Any]:
    current_year = datetime.now().year
    if tool_name == "analyze_portfolio_performance":
        return {"time_period": _extract_date_range(user_query, "ytd")}
    if tool_name == "categorize_transactions":
        return {"date_range": _extract_date_range(user_query, "max")}
    if tool_name == "estimate_capital_gains_tax":
        return {
            "tax_year": _extract_tax_year(user_query, current_year),
            "income_bracket": _extract_income_bracket(user_query, "middle"),
        }
    if tool_name == "check_compliance":
        return {"check_type": _extract_check_type(user_query, "all")}
    if tool_name == "get_market_data":
        symbols = _extract_symbols(user_query)
        args: dict[str, Any] = {"metrics": ["price", "change", "change_percent", "currency", "market_value"]}
        if symbols:
            args["symbols"] = symbols
        return args

    return {"target_profile": _extract_target_profile(user_query, "balanced")}


def _sanitize_tool_args(
    tool_name: ToolName,
    user_query: str,
    tool_args: dict[str, Any] | None,
) -> dict[str, Any]:
    merged_args = _default_args_for_tool(tool_name, user_query)
    if isinstance(tool_args, dict):
        merged_args.update(tool_args)

    if tool_name == "analyze_portfolio_performance":
        value = merged_args.get("time_period")
        if value not in VALID_DATE_RANGES:
            merged_args["time_period"] = "ytd"
    elif tool_name == "categorize_transactions":
        value = merged_args.get("date_range")
        if value not in VALID_DATE_RANGES:
            merged_args["date_range"] = "max"
    elif tool_name == "estimate_capital_gains_tax":
        year = merged_args.get("tax_year")
        if not isinstance(year, int):
            merged_args["tax_year"] = datetime.now().year

        bracket = merged_args.get("income_bracket")
        if not isinstance(bracket, str) or bracket not in _VALID_INCOME_BRACKETS:
            merged_args["income_bracket"] = "middle"
    elif tool_name == "check_compliance":
        check_type = merged_args.get("check_type")
        if not isinstance(check_type, str) or check_type not in _VALID_CHECK_TYPES:
            merged_args["check_type"] = "all"
    elif tool_name == "get_market_data":
        symbols = merged_args.get("symbols")
        if symbols is not None and not isinstance(symbols, list):
            merged_args["symbols"] = None
        metrics = merged_args.get("metrics")
        if not isinstance(metrics, list):
            merged_args["metrics"] = ["price", "change", "change_percent", "currency", "market_value"]
    else:
        profile = merged_args.get("target_profile")
        if not isinstance(profile, str) or profile not in _VALID_TARGET_PROFILES:
            merged_args["target_profile"] = "balanced"

    return merged_args


def _route_from_keywords(user_query: str) -> RouteName:
    lowered_query = user_query.lower()
    if not lowered_query:
        return "clarify"

    if any(marker in lowered_query for marker in _PROMPT_INJECTION_MARKERS):
        return "clarify"

    matched_routes: list[RouteName] = []
    for route_name, keywords in _ROUTER_INTENTS.items():
        if route_name == "clarify":
            continue

        if any(keyword in lowered_query for keyword in keywords):
            matched_routes.append(route_name)

    if len(matched_routes) == 1:
        return matched_routes[0]

    return "clarify"


async def keyword_router(user_query: str, messages: list[Any]) -> dict[str, Any]:
    """Deterministic fallback router used when an LLM router is not injected."""
    del messages
    route = _route_from_keywords(user_query)
    if route == "clarify":
        return {
            "route": "clarify",
            "tool_name": None,
            "tool_args": {},
            "reason": "ambiguous_or_out_of_scope",
        }

    tool_name = _ROUTE_TO_TOOL[route]
    return {
        "route": route,
        "tool_name": tool_name,
        "tool_args": _default_args_for_tool(tool_name, user_query),
        "reason": "keyword_match",
    }


def _normalize_router_decision(user_query: str, decision: dict[str, Any]) -> dict[str, Any]:
    normalized_route: RouteName = "clarify"
    route_value = decision.get("route")
    if isinstance(route_value, str) and route_value in _VALID_ROUTES:
        normalized_route = cast(RouteName, route_value)

    if normalized_route == "clarify":
        return {"route": "clarify", "tool_name": None, "tool_args": {}}

    default_tool_name = _ROUTE_TO_TOOL[normalized_route]
    proposed_tool_name = decision.get("tool_name")
    tool_name = (
        proposed_tool_name
        if isinstance(proposed_tool_name, str) and proposed_tool_name in _TOOL_FUNCTIONS
        else default_tool_name
    )
    tool_args_value = decision.get("tool_args")
    tool_args = tool_args_value if isinstance(tool_args_value, dict) else None
    sanitized_tool_args = _sanitize_tool_args(tool_name, user_query, tool_args)
    return {
        "route": normalized_route,
        "tool_name": tool_name,
        "tool_args": sanitized_tool_args,
    }


def _is_follow_up_query(user_query: str) -> bool:
    lowered_query = user_query.lower()
    return any(marker in lowered_query for marker in _FOLLOW_UP_MARKERS)


def _route_from_recent_tool_history(
    state: AgentState,
    user_query: str,
) -> dict[str, Any] | None:
    history = state.get("tool_call_history")
    if not isinstance(history, list) or not history:
        return None

    for record in reversed(history):
        if not isinstance(record, dict):
            continue

        route = record.get("route")
        tool_name = record.get("tool_name")
        if (
            isinstance(route, str)
            and route in _VALID_ROUTES
            and route != "clarify"
            and isinstance(tool_name, str)
            and tool_name in _TOOL_FUNCTIONS
        ):
            prior_args = record.get("tool_args")
            merged_args = _sanitize_tool_args(
                cast(ToolName, tool_name),
                user_query,
                prior_args if isinstance(prior_args, dict) else None,
            )
            return {
                "route": cast(RouteName, route),
                "tool_name": cast(ToolName, tool_name),
                "tool_args": merged_args,
            }

    return None


def _route_from_recent_messages(messages: list[Any]) -> RouteName | None:
    if len(messages) < 2:
        return None

    for message in reversed(messages[:-1]):
        if not _is_human_message(message):
            continue

        route = _route_from_keywords(_message_to_text(message).strip())
        if route != "clarify":
            return route

    return None


def make_router_node(dependencies: NodeDependencies) -> Callable[[AgentState], Awaitable[AgentState]]:
    """Builds the Router node with injected routing dependency."""

    async def router_node(state: AgentState) -> AgentState:
        messages = state.get("messages", [])
        user_query = _latest_user_query(messages)
        try:
            decision = await dependencies.router(user_query, messages)
        except Exception:
            decision = await keyword_router(user_query, messages)
        normalized_decision = _normalize_router_decision(user_query, decision)
        route = normalized_decision["route"]
        if route == "clarify":
            if _is_follow_up_query(user_query):
                recovered_decision = _route_from_recent_tool_history(state, user_query)
                if recovered_decision is None:
                    recovered_route = _route_from_recent_messages(messages)
                    if recovered_route is not None and recovered_route != "clarify":
                        recovered_tool = _ROUTE_TO_TOOL[recovered_route]
                        recovered_decision = {
                            "route": recovered_route,
                            "tool_name": recovered_tool,
                            "tool_args": _sanitize_tool_args(
                                recovered_tool,
                                user_query,
                                None,
                            ),
                        }
                if recovered_decision is not None:
                    return {
                        "route": recovered_decision["route"],
                        "tool_name": recovered_decision["tool_name"],
                        "tool_args": recovered_decision["tool_args"],
                        "tool_result": None,
                        "error": None,
                        "pending_action": "tool_selected",
                    }

            return {
                "route": "clarify",
                "tool_name": None,
                "tool_args": {},
                "tool_result": None,
                "error": None,
                "pending_action": "ambiguous_or_unsupported",
            }

        return {
            "route": route,
            "tool_name": normalized_decision["tool_name"],
            "tool_args": normalized_decision["tool_args"],
            "tool_result": None,
            "error": None,
            "pending_action": "tool_selected",
        }

    return router_node


def make_tool_executor_node(
    dependencies: NodeDependencies,
) -> Callable[[AgentState], Awaitable[AgentState]]:
    """Builds Tool Executor node that calls selected tools."""

    async def tool_executor_node(state: AgentState) -> AgentState:
        tool_name = state.get("tool_name")
        tool_args = state.get("tool_args", {})
        route = state.get("route", "clarify")
        history = list(state.get("tool_call_history", []))

        if not isinstance(tool_name, str) or tool_name not in _TOOL_FUNCTIONS:
            tool_result = ToolResult.fail("UNSUPPORTED_TOOL")
        else:
            tool_function = _TOOL_FUNCTIONS[tool_name]
            try:
                tool_result = await tool_function(dependencies.api_client, **tool_args)
            except TypeError as _te:
                fallback_args = _default_args_for_tool(tool_name, "")
                try:
                    tool_result = await tool_function(dependencies.api_client, **fallback_args)
                except Exception as _fe:
                    tool_result = ToolResult.fail("API_ERROR")
            except Exception as _ex:
                tool_result = ToolResult.fail("API_ERROR")

        history.append(
            {
                "route": route,
                "tool_name": tool_name,
                "tool_args": tool_args if isinstance(tool_args, dict) else {},
                "success": tool_result.success,
                "error": tool_result.error,
            }
        )

        return {
            "tool_result": tool_result,
            "tool_call_history": history,
        }

    return tool_executor_node


def _payload_has_only_finite_numbers(payload: Any) -> bool:
    if isinstance(payload, bool):
        return True
    if isinstance(payload, (int, float)):
        return math.isfinite(float(payload))
    if isinstance(payload, dict):
        return all(_payload_has_only_finite_numbers(value) for value in payload.values())
    if isinstance(payload, list):
        return all(_payload_has_only_finite_numbers(value) for value in payload)

    return True


def _validate_portfolio_payload(payload: dict[str, Any]) -> str | None:
    performance = payload.get("performance")
    if not isinstance(performance, dict):
        return "INVALID_PERFORMANCE_PAYLOAD"

    net_performance_pct = performance.get("netPerformancePercentage")
    if isinstance(net_performance_pct, (int, float)):
        if net_performance_pct < -100 or net_performance_pct > 10000:
            return "UNSANE_RETURN_VALUE"

    return None


def _validate_transaction_payload(payload: dict[str, Any]) -> str | None:
    total_transactions = payload.get("total_transactions")
    if not isinstance(total_transactions, int) or total_transactions < 0:
        return "INVALID_TRANSACTION_COUNT"

    return None


def _validate_tax_payload(payload: dict[str, Any]) -> str | None:
    combined_liability = payload.get("combined_liability")
    if not isinstance(combined_liability, (int, float)):
        return "INVALID_TAX_PAYLOAD"
    if combined_liability < 0:
        return "INVALID_TAX_PAYLOAD"

    return None


def _validate_allocation_payload(payload: dict[str, Any]) -> str | None:
    holdings_count = payload.get("holdings_count")
    if not isinstance(holdings_count, int) or holdings_count < 0:
        return "INVALID_HOLDINGS_COUNT"

    current_allocation = payload.get("current_allocation")
    if not isinstance(current_allocation, dict) or not current_allocation:
        return "INVALID_ALLOCATION_PAYLOAD"

    allocation_values: list[float] = []
    for value in current_allocation.values():
        if not isinstance(value, (int, float)):
            return "INVALID_ALLOCATION_PAYLOAD"
        allocation_values.append(float(value))

    if holdings_count > 0 and abs(sum(allocation_values) - 100.0) > 1.0:
        return "INVALID_ALLOCATION_SUM"

    return None


def _validate_compliance_payload(payload: dict[str, Any]) -> str | None:
    total_violations = payload.get("total_violations")
    if not isinstance(total_violations, int) or total_violations < 0:
        return "INVALID_COMPLIANCE_PAYLOAD"
    total_warnings = payload.get("total_warnings")
    if not isinstance(total_warnings, int) or total_warnings < 0:
        return "INVALID_COMPLIANCE_PAYLOAD"
    return None


def _validate_market_data_payload(payload: dict[str, Any]) -> str | None:
    total_holdings = payload.get("total_holdings")
    if not isinstance(total_holdings, int) or total_holdings < 0:
        return "INVALID_MARKET_DATA_PAYLOAD"
    holdings = payload.get("holdings")
    if not isinstance(holdings, list):
        return "INVALID_MARKET_DATA_PAYLOAD"
    return None


def _validate_tool_payload(tool_name: ToolName, payload: dict[str, Any]) -> str | None:
    if tool_name == "analyze_portfolio_performance":
        return _validate_portfolio_payload(payload)
    if tool_name == "categorize_transactions":
        return _validate_transaction_payload(payload)
    if tool_name == "estimate_capital_gains_tax":
        return _validate_tax_payload(payload)
    if tool_name == "check_compliance":
        return _validate_compliance_payload(payload)
    if tool_name == "get_market_data":
        return _validate_market_data_payload(payload)

    return _validate_allocation_payload(payload)


def make_validator_node() -> Callable[[AgentState], AgentState]:
    """Builds Validator node for ToolResult success/data checks."""

    def validator_node(state: AgentState) -> AgentState:
        tool_result = state.get("tool_result")
        tool_name = state.get("tool_name")
        if tool_result is None:
            return {"pending_action": "invalid_or_error", "error": "NO_TOOL_RESULT"}

        if not tool_result.success:
            return {
                "pending_action": "invalid_or_error",
                "error": tool_result.error or "API_ERROR",
            }

        if not isinstance(tool_name, str):
            return {"pending_action": "invalid_or_error", "error": "UNSUPPORTED_TOOL"}

        payload = tool_result.data
        if not isinstance(payload, dict) or not payload:
            return {"pending_action": "invalid_or_error", "error": "EMPTY_TOOL_PAYLOAD"}

        if not _payload_has_only_finite_numbers(payload):
            return {"pending_action": "invalid_or_error", "error": "NON_FINITE_VALUE"}

        validation_error = _validate_tool_payload(tool_name, payload)
        if validation_error is not None:
            return {"pending_action": "invalid_or_error", "error": validation_error}

        return {"pending_action": "valid", "error": None}

    return validator_node


def _format_currency(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):,.2f}"
    return "n/a"


def _build_summary(tool_name: ToolName | None, tool_result: ToolResult | None) -> str:
    if tool_name is None or tool_result is None or not isinstance(tool_result.data, dict):
        return "Analysis complete."

    payload = tool_result.data
    if tool_name == "analyze_portfolio_performance":
        performance = payload.get("performance", {})
        if isinstance(performance, dict):
            net_pct = performance.get("netPerformancePercentage")
            if isinstance(net_pct, (int, float)):
                return f"Portfolio net performance is {net_pct:.2f}% for the selected range."

        return "Portfolio performance data is ready."

    if tool_name == "categorize_transactions":
        total_transactions = payload.get("total_transactions")
        if isinstance(total_transactions, int):
            return (
                "Transaction categorization is complete. "
                f"I found {total_transactions} activities in the selected range."
            )
        return "Transaction categorization is complete."

    if tool_name == "estimate_capital_gains_tax":
        liability = payload.get("combined_liability")
        tax_year = payload.get("tax_year")
        return (
            "Capital gains estimate is ready. "
            f"Estimated combined liability for {tax_year} is {_format_currency(liability)}."
        )

    if tool_name == "check_compliance":
        total_violations = payload.get("total_violations", 0)
        total_warnings = payload.get("total_warnings", 0)
        return (
            "Compliance screening is complete. "
            f"Found {total_violations} violation(s) and {total_warnings} warning(s)."
        )

    if tool_name == "get_market_data":
        total_holdings = payload.get("total_holdings", 0)
        total_value = payload.get("total_market_value")
        value_str = f" with total value ${_format_currency(total_value)}" if total_value else ""
        return (
            "Market data retrieved. "
            f"Showing data for {total_holdings} holding(s){value_str}."
        )

    warnings = payload.get("concentration_warnings")
    warning_count = len(warnings) if isinstance(warnings, list) else 0
    return (
        "Allocation analysis is complete. "
        f"I found {warning_count} concentration warning(s)."
    )


def make_synthesizer_node(
    dependencies: NodeDependencies | None = None,
) -> Callable[[AgentState], AgentState | Awaitable[AgentState]]:
    """Builds Synthesizer node. Uses LLM when a synthesizer callable is available."""

    synthesizer_fn = dependencies.synthesizer if dependencies else None

    async def synthesizer_node(state: AgentState) -> AgentState:
        tool_name = state.get("tool_name")
        tool_result = state.get("tool_result")

        if synthesizer_fn is not None and tool_result is not None:
            try:
                tool_json = json.dumps(tool_result.data, default=str)[:4000]
                user_query = ""
                messages = state.get("messages")
                if isinstance(messages, list):
                    for msg in reversed(messages):
                        text = _message_to_text(msg)
                        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
                        if role == "user" and text:
                            user_query = text
                            break
                prompt_context = (
                    f"User asked: {user_query}\n\n"
                    f"Tool used: {tool_name}\n\n"
                    f"Tool result (JSON):\n{tool_json}"
                )
                summary = await synthesizer_fn(SYNTHESIS_PROMPT, prompt_context)
            except Exception:
                summary = _build_summary(tool_name, tool_result)
        else:
            summary = _build_summary(tool_name, tool_result)

        final_response: dict[str, Any] = {
            "category": "analysis",
            "message": summary,
            "tool_name": tool_name,
            "data": tool_result.data if tool_result is not None else None,
            "suggestions": [],
        }
        return {
            "final_response": final_response,
            "messages": [_assistant_message(summary)],
            "pending_action": "valid",
        }

    return synthesizer_node


def make_clarifier_node() -> Callable[[AgentState], AgentState]:
    """Builds Clarifier node for ambiguous or unsupported requests."""

    def clarifier_node(state: AgentState) -> AgentState:
        del state
        capabilities_block = "\n".join(f"- {capability}" for capability in SUPPORTED_CAPABILITIES)
        message = (
            "I can help with financial analysis inside Ghostfolio, but I could not map that request "
            "to one supported tool.\n\n"
            "Supported capabilities:\n"
            f"{capabilities_block}\n\n"
            "Try asking: 'How is my portfolio doing ytd?' or "
            "'Am I diversified enough for a balanced profile?'"
        )
        return {
            "final_response": {
                "category": "clarification",
                "message": message,
                "tool_name": None,
                "data": None,
                "suggestions": [
                    "How is my portfolio doing ytd?",
                    "Categorize my transactions for max range.",
                    "Estimate my 2025 capital gains tax in middle bracket.",
                    "Analyze my allocation with a balanced profile.",
                ],
            },
            "messages": [_assistant_message(message)],
            "pending_action": "ambiguous_or_unsupported",
            "error": None,
        }

    return clarifier_node


_ERROR_MESSAGES: Final[dict[str, str]] = {
    "INVALID_TIME_PERIOD": "Please use a valid period such as ytd, 1y, or max.",
    "INVALID_TAX_YEAR": "Tax year must be between 2020 and the current year.",
    "INVALID_INCOME_BRACKET": "Income bracket must be low, middle, or high.",
    "INVALID_TARGET_PROFILE": "Target profile must be conservative, balanced, or aggressive.",
    "EMPTY_PORTFOLIO": (
        "No holdings found. Use the 'Load Sample Portfolio' button on the home page,"
        " or add your own investments in Ghostfolio."
    ),
    "API_TIMEOUT": "I could not reach Ghostfolio in time. Please check that it is running.",
    "API_ERROR": "Received an error from the portfolio service. Please try again.",
    "AUTH_REQUIRED": "Please sign in or create an account to get portfolio insights.",
    "AUTH_FAILED": "Your session has expired. Please sign in again.",
    "UNSUPPORTED_TOOL": "I could not map your request to a supported tool.",
    "EMPTY_TOOL_PAYLOAD": "I received an empty response and could not continue safely.",
    "NON_FINITE_VALUE": "I received invalid numeric values and stopped safely.",
    "INVALID_PERFORMANCE_PAYLOAD": "Performance data came back in an unexpected format.",
    "INVALID_TRANSACTION_COUNT": "Transaction data looked incomplete or malformed.",
    "INVALID_TAX_PAYLOAD": "Tax estimate data came back in an unexpected format.",
    "INVALID_ALLOCATION_PAYLOAD": "Allocation data came back in an unexpected format.",
    "INVALID_HOLDINGS_COUNT": "Holdings count was invalid, so I stopped safely.",
    "INVALID_ALLOCATION_SUM": "Allocation percentages do not form a sane total (~100%).",
    "INVALID_CHECK_TYPE": "Check type must be all, wash_sale, pattern_day_trading, or concentration.",
    "INVALID_COMPLIANCE_PAYLOAD": "Compliance check data came back in an unexpected format.",
    "INVALID_METRIC": "One or more requested metrics are not supported.",
    "INVALID_MARKET_DATA_PAYLOAD": "Market data came back in an unexpected format.",
    "SYMBOLS_NOT_FOUND": "None of the requested symbols were found in your portfolio.",
}


def make_error_handler_node() -> Callable[[AgentState], AgentState]:
    """Builds Error Handler node for user-safe recovery guidance."""

    def error_handler_node(state: AgentState) -> AgentState:
        tool_result = state.get("tool_result")
        error_code = state.get("error")
        if not error_code and tool_result is not None:
            error_code = tool_result.error
        if error_code is None:
            error_code = "API_ERROR"

        safe_message = _ERROR_MESSAGES.get(
            error_code,
            "I ran into an issue while analyzing your request. Please try a narrower query.",
        )
        message = (
            f"{safe_message}\n\n"
            "You can try again with one focused request, for example: "
            "'Show my portfolio performance for ytd.'"
        )
        return {
            "final_response": {
                "category": "error",
                "message": message,
                "tool_name": state.get("tool_name"),
                "data": None,
                "suggestions": [
                    "Show my portfolio performance for ytd.",
                    "Categorize my transactions for max range.",
                    "Estimate my capital gains tax for this year.",
                ],
            },
            "messages": [_assistant_message(message)],
            "pending_action": "invalid_or_error",
        }

    return error_handler_node


def route_after_router(state: AgentState) -> str:
    """Returns edge key from Router node to next node."""
    if state.get("pending_action") == "tool_selected":
        return "tool_selected"

    return "ambiguous_or_unsupported"


def route_after_validator(state: AgentState) -> str:
    """Returns edge key from Validator node to terminal node."""
    if state.get("pending_action") == "valid":
        return "valid"

    return "invalid_or_error"
