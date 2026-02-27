"""Graph builder for the AgentForge LangGraph topology."""

from __future__ import annotations

import inspect
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

try:
    from langgraph.graph import END, START, StateGraph
    from langgraph.checkpoint.memory import MemorySaver
except ModuleNotFoundError:
    START = "__start__"
    END = "__end__"
    MemorySaver = None

try:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
except ModuleNotFoundError:
    AsyncSqliteSaver = None

    class _FallbackDrawableGraph:
        def __init__(
            self,
            edges: dict[str, list[str]],
            conditional_edges: dict[str, tuple[Callable[[dict[str, Any]], str], dict[str, str]]],
        ) -> None:
            self._edges = edges
            self._conditional_edges = conditional_edges

        def draw_mermaid(self) -> str:
            lines = ["flowchart TD"]
            for source, targets in self._edges.items():
                source_label = "START" if source == START else source
                for target in targets:
                    target_label = "END" if target == END else target
                    lines.append(f"{source_label} --> {target_label}")

            for source, (_, mapping) in self._conditional_edges.items():
                for edge_label, target in mapping.items():
                    target_label = "END" if target == END else target
                    lines.append(f'{source} -->|"{edge_label}"| {target_label}')

            return "\n".join(lines)

    class _FallbackCompiledGraph:
        def __init__(
            self,
            nodes: dict[str, Callable[[dict[str, Any]], Any]],
            edges: dict[str, list[str]],
            conditional_edges: dict[str, tuple[Callable[[dict[str, Any]], str], dict[str, str]]],
        ) -> None:
            self._nodes = nodes
            self._edges = edges
            self._conditional_edges = conditional_edges
            self._thread_states: dict[str, dict[str, Any]] = {}

        async def ainvoke(
            self,
            state: dict[str, Any],
            config: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            thread_id = self._thread_id_from_config(config)
            if thread_id and thread_id in self._thread_states:
                merged_state = self._merge_state(self._thread_states[thread_id], state)
            else:
                merged_state = dict(state)
            next_nodes = self._edges.get(START, [])
            current = next_nodes[0] if next_nodes else END

            while current != END:
                node = self._nodes[current]
                update = node(merged_state)
                if inspect.isawaitable(update):
                    update = await update

                if isinstance(update, dict):
                    merged_state = self._merge_state(merged_state, update)

                if current in self._conditional_edges:
                    chooser, mapping = self._conditional_edges[current]
                    edge_key = chooser(merged_state)
                    current = mapping.get(edge_key, END)
                    continue

                linear_targets = self._edges.get(current, [])
                current = linear_targets[0] if linear_targets else END

            if thread_id:
                self._thread_states[thread_id] = dict(merged_state)

            return merged_state

        def get_graph(self) -> _FallbackDrawableGraph:
            return _FallbackDrawableGraph(self._edges, self._conditional_edges)

        @staticmethod
        def _merge_state(state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
            merged = dict(state)
            for key, value in update.items():
                if (
                    key == "messages"
                    and isinstance(merged.get("messages"), list)
                    and isinstance(value, list)
                ):
                    merged["messages"] = [*merged["messages"], *value]
                else:
                    merged[key] = value

            return merged

        @staticmethod
        def _thread_id_from_config(config: dict[str, Any] | None) -> str | None:
            if not isinstance(config, dict):
                return None

            configurable = config.get("configurable")
            if not isinstance(configurable, dict):
                return None

            thread_id = configurable.get("thread_id")
            if isinstance(thread_id, str) and thread_id:
                return thread_id

            return None

    class StateGraph:
        def __init__(self, state_type: Any) -> None:
            del state_type
            self._nodes: dict[str, Callable[[dict[str, Any]], Any]] = {}
            self._edges: dict[str, list[str]] = {}
            self._conditional_edges: dict[
                str, tuple[Callable[[dict[str, Any]], str], dict[str, str]]
            ] = {}

        def add_node(self, name: str, node: Callable[[dict[str, Any]], Any]) -> None:
            self._nodes[name] = node

        def add_edge(self, start_node: str, end_node: str) -> None:
            self._edges.setdefault(start_node, []).append(end_node)

        def add_conditional_edges(
            self,
            start_node: str,
            chooser: Callable[[dict[str, Any]], str],
            mapping: dict[str, str],
        ) -> None:
            self._conditional_edges[start_node] = (chooser, mapping)

        def compile(self, checkpointer: Any | None = None) -> _FallbackCompiledGraph:
            del checkpointer
            return _FallbackCompiledGraph(
                nodes=dict(self._nodes),
                edges={key: list(value) for key, value in self._edges.items()},
                conditional_edges={
                    key: (chooser, dict(mapping))
                    for key, (chooser, mapping) in self._conditional_edges.items()
                },
            )

from agent.graph.nodes import (
    NodeDependencies,
    RouterCallable,
    SynthesizerCallable,
    keyword_router,
    make_clarifier_node,
    make_error_handler_node,
    make_router_node,
    make_synthesizer_node,
    make_tool_executor_node,
    make_validator_node,
    route_after_router,
    route_after_validator,
)
from agent.graph.state import AgentState

_SHARED_CHECKPOINTER: Any = None
_CHECKPOINTER_INITIALIZED: bool = False


def _resolve_sqlite_path() -> str:
    """Returns the SQLite DB path for the persistent checkpointer.

    Uses ``LANGGRAPH_SQLITE_PATH`` env var if set, otherwise writes to
    ``agent/.data/checkpoints.db`` (relative to the repo root).
    """
    custom_path = os.getenv("LANGGRAPH_SQLITE_PATH")
    if custom_path:
        return custom_path

    data_dir = Path(__file__).resolve().parent.parent / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "checkpoints.db")


async def _get_checkpointer() -> Any:
    """Returns a persistent SQLite checkpointer, falling back to in-memory."""
    global _SHARED_CHECKPOINTER, _CHECKPOINTER_INITIALIZED

    if _CHECKPOINTER_INITIALIZED:
        return _SHARED_CHECKPOINTER

    _CHECKPOINTER_INITIALIZED = True

    # Try persistent SQLite first
    if AsyncSqliteSaver is not None:
        try:
            db_path = _resolve_sqlite_path()
            checkpointer = AsyncSqliteSaver.from_conn_string(db_path)
            await checkpointer.setup()
            _SHARED_CHECKPOINTER = checkpointer
            return _SHARED_CHECKPOINTER
        except Exception:
            pass

    # Fallback to in-memory
    if MemorySaver is not None:
        _SHARED_CHECKPOINTER = MemorySaver()

    return _SHARED_CHECKPOINTER


async def build_graph(
    api_client: Any,
    router: RouterCallable | None = None,
    synthesizer: SynthesizerCallable | None = None,
) -> Any:
    """Builds and compiles the 6-node AgentForge graph.

    Args:
        api_client: Injected Ghostfolio API client dependency.
        router: Optional injected router callable (LLM-backed or mocked in tests).
        synthesizer: Optional LLM-backed callable for rich response generation.

    Returns:
        A compiled LangGraph executable.
    """
    dependencies = NodeDependencies(
        api_client=api_client,
        router=router or keyword_router,
        synthesizer=synthesizer,
    )

    graph = StateGraph(AgentState)
    graph.add_node("router", make_router_node(dependencies))
    graph.add_node("tool_executor", make_tool_executor_node(dependencies))
    graph.add_node("validator", make_validator_node())
    graph.add_node("synthesizer", make_synthesizer_node(dependencies))
    graph.add_node("clarifier", make_clarifier_node())
    graph.add_node("error_handler", make_error_handler_node())

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "tool_selected": "tool_executor",
            "ambiguous_or_unsupported": "clarifier",
        },
    )
    graph.add_edge("tool_executor", "validator")
    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {
            "valid": "synthesizer",
            "invalid_or_error": "error_handler",
        },
    )
    graph.add_edge("clarifier", END)
    graph.add_edge("synthesizer", END)
    graph.add_edge("error_handler", END)

    checkpointer = await _get_checkpointer()
    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


def draw_graph_mermaid(compiled_graph: Any) -> str:
    """Returns Mermaid markup for the compiled graph."""
    return compiled_graph.get_graph().draw_mermaid()
