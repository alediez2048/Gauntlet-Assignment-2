from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio

from agent import main as main_module


class _StubGraph:
    def __init__(
        self,
        *,
        state: dict[str, Any] | None = None,
        exception: Exception | None = None,
    ) -> None:
        self._state = state or {}
        self._exception = exception
        self.received_state: dict[str, Any] | None = None
        self.received_config: dict[str, Any] | None = None

    async def ainvoke(
        self,
        state: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.received_state = state
        self.received_config = config
        if self._exception is not None:
            raise self._exception

        return self._state


@pytest_asyncio.fixture
async def async_client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=main_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def _patch_graph(monkeypatch: pytest.MonkeyPatch, graph: _StubGraph) -> None:
    monkeypatch.setattr(main_module, "build_graph", lambda api_client: graph)


def _parse_sse_events(raw_stream: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    blocks = [block for block in raw_stream.split("\n\n") if block.strip()]
    for block in blocks:
        event_type: str | None = None
        payload: dict[str, Any] = {}
        for line in block.splitlines():
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                payload = json.loads(line.split(":", 1)[1].strip())

        if event_type is not None:
            events.append({"event": event_type, "data": payload})

    return events


async def _collect_sse_events(
    async_client: httpx.AsyncClient,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    async with async_client.stream("POST", "/api/agent/chat", json=payload) as response:
        assert response.status_code == 200
        stream_chunks: list[str] = []
        async for chunk in response.aiter_text():
            stream_chunks.append(chunk)

    return _parse_sse_events("".join(stream_chunks))


def _successful_graph_state() -> dict[str, Any]:
    return {
        "tool_call_history": [
            {
                "route": "portfolio",
                "tool_name": "analyze_portfolio_performance",
                "tool_args": {"time_period": "ytd"},
                "success": True,
                "error": None,
            }
        ],
        "error": None,
        "final_response": {
            "category": "analysis",
            "message": (
                "Portfolio net performance is 8.12% for the selected range. "
                "Risk-adjusted return remains stable."
            ),
            "tool_name": "analyze_portfolio_performance",
            "data": {"performance": {"netPerformancePercentage": 8.12}},
            "suggestions": [],
        },
    }


@pytest.mark.asyncio
async def test_chat_sse_emits_thinking_first(
    async_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_graph = _StubGraph(state=_successful_graph_state())
    _patch_graph(monkeypatch, stub_graph)

    events = await _collect_sse_events(
        async_client,
        {"message": "How is my portfolio doing ytd?"},
    )
    assert events[0]["event"] == "thinking"
    assert events[0]["data"] == {"message": "Analyzing your request..."}


@pytest.mark.asyncio
async def test_chat_sse_emits_done_last_on_success(
    async_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_graph = _StubGraph(state=_successful_graph_state())
    _patch_graph(monkeypatch, stub_graph)

    events = await _collect_sse_events(
        async_client,
        {"message": "How is my portfolio doing ytd?"},
    )
    event_types = [event["event"] for event in events]

    assert event_types[-1] == "done"
    assert event_types[:3] == ["thinking", "tool_call", "tool_result"]
    assert "token" in event_types[3:-1]

    done_payload = events[-1]["data"]
    assert isinstance(done_payload["thread_id"], str)
    assert done_payload["thread_id"]
    assert done_payload["response"]["category"] == "analysis"
    assert isinstance(done_payload["tool_call_history"], list)

    assert stub_graph.received_state is not None
    assert stub_graph.received_state["messages"][0]["content"] == "How is my portfolio doing ytd?"
    assert stub_graph.received_config == {
        "configurable": {"thread_id": done_payload["thread_id"]}
    }


@pytest.mark.asyncio
async def test_chat_sse_tool_event_payload_shapes(
    async_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_graph = _StubGraph(state=_successful_graph_state())
    _patch_graph(monkeypatch, stub_graph)

    events = await _collect_sse_events(
        async_client,
        {"message": "How is my portfolio doing ytd?"},
    )

    tool_call_payload = events[1]["data"]
    assert tool_call_payload == {
        "tool": "analyze_portfolio_performance",
        "args": {"time_period": "ytd"},
    }

    tool_result_payload = events[2]["data"]
    assert tool_result_payload == {
        "tool": "analyze_portfolio_performance",
        "success": True,
    }

    token_payloads = [event["data"] for event in events if event["event"] == "token"]
    assert token_payloads
    assert all(isinstance(payload.get("content"), str) and payload["content"] for payload in token_payloads)


@pytest.mark.asyncio
async def test_chat_sse_reuses_provided_thread_id(
    async_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_graph = _StubGraph(state=_successful_graph_state())
    _patch_graph(monkeypatch, stub_graph)

    events = await _collect_sse_events(
        async_client,
        {
            "message": "Based on that, where am I most concentrated?",
            "thread_id": "thread-continuity-1",
        },
    )

    done_payload = events[-1]["data"]
    assert done_payload["thread_id"] == "thread-continuity-1"
    assert stub_graph.received_config == {
        "configurable": {"thread_id": "thread-continuity-1"}
    }


@pytest.mark.asyncio
async def test_chat_sse_emits_error_and_closes_on_graph_exception(
    async_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_graph = _StubGraph(exception=RuntimeError("unexpected failure"))
    _patch_graph(monkeypatch, stub_graph)

    events = await _collect_sse_events(
        async_client,
        {"message": "How is my portfolio doing ytd?"},
    )
    assert [event["event"] for event in events] == ["thinking", "error"]
    assert events[-1]["data"]["code"] == "API_ERROR"
    assert events[-1]["data"]["message"] == "Received an error from the portfolio service."
