"""FastAPI application entrypoint for AgentForge."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from agent.clients.ghostfolio_client import GhostfolioClient
from agent.graph.graph import build_graph
app = FastAPI(title="AgentForge", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3333", "http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_SAFE_ERROR_MESSAGES: dict[str, str] = {
    "INVALID_TIME_PERIOD": "Please use a valid period such as ytd, 1y, or max.",
    "INVALID_TAX_YEAR": "Tax year must be between 2020 and the current year.",
    "API_TIMEOUT": "Having trouble reaching portfolio data. Is Ghostfolio running?",
    "API_ERROR": "Received an error from the portfolio service.",
    "EMPTY_PORTFOLIO": "No holdings found. Add investments to Ghostfolio first.",
    "AUTH_FAILED": "Authentication failed. Check GHOSTFOLIO_ACCESS_TOKEN.",
}


class ChatRequest(BaseModel):
    """Incoming payload for `POST /api/agent/chat`."""

    message: str = Field(min_length=1)
    thread_id: str | None = None

    @field_validator("message")
    @classmethod
    def _validate_message(cls, value: str) -> str:
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("message must not be empty.")

        return stripped_value


def _serialize_sse_event(event_type: str, payload: dict[str, Any]) -> str:
    """Formats one server-sent event frame."""
    serialized_payload = json.dumps(payload, separators=(",", ":"))
    return f"event: {event_type}\ndata: {serialized_payload}\n\n"


def _chunk_text(content: str, *, chunk_size: int = 64) -> list[str]:
    """Splits a response string into deterministic SSE token chunks."""
    if not content:
        return []

    return [content[index:index + chunk_size] for index in range(0, len(content), chunk_size)]


def _coerce_tool_call_history(raw_history: Any) -> list[dict[str, Any]]:
    """Normalizes tool call history into a serializable list of dictionaries."""
    if not isinstance(raw_history, list):
        return []

    normalized_history: list[dict[str, Any]] = []
    for item in raw_history:
        if isinstance(item, dict):
            normalized_history.append(item)

    return normalized_history


def _safe_error_message(error_code: str) -> str:
    """Returns a user-safe message for a known error code."""
    return _SAFE_ERROR_MESSAGES.get(
        error_code,
        "I ran into an issue while analyzing your request. Please try again.",
    )


def _resolve_error_code(state: dict[str, Any], tool_history: list[dict[str, Any]]) -> str:
    """Extracts an error code from graph output state."""
    error_value = state.get("error")
    if isinstance(error_value, str) and error_value:
        return error_value

    if tool_history:
        latest_error = tool_history[-1].get("error")
        if isinstance(latest_error, str) and latest_error:
            return latest_error

    return "API_ERROR"


def _map_graph_state_to_events(
    state: dict[str, Any],
    *,
    thread_id: str,
) -> list[tuple[str, dict[str, Any]]]:
    """Maps graph output state to frontend-facing SSE events."""
    events: list[tuple[str, dict[str, Any]]] = []
    tool_history = _coerce_tool_call_history(state.get("tool_call_history"))

    for record in tool_history:
        tool_name = record.get("tool_name")
        normalized_tool_name = tool_name if isinstance(tool_name, str) else "unknown_tool"
        tool_args = record.get("tool_args")
        normalized_tool_args = tool_args if isinstance(tool_args, dict) else {}
        success = bool(record.get("success"))

        events.append(
            (
                "tool_call",
                {"tool": normalized_tool_name, "args": normalized_tool_args},
            )
        )

        result_payload: dict[str, Any] = {"tool": normalized_tool_name, "success": success}
        tool_error = record.get("error")
        if isinstance(tool_error, str) and tool_error:
            result_payload["error"] = tool_error

        events.append(("tool_result", result_payload))

    final_response = state.get("final_response")
    if not isinstance(final_response, dict):
        error_code = _resolve_error_code(state, tool_history)
        return [
            *events,
            ("error", {"code": error_code, "message": _safe_error_message(error_code)}),
        ]

    category = final_response.get("category")
    if category == "error":
        error_code = _resolve_error_code(state, tool_history)
        return [
            *events,
            ("error", {"code": error_code, "message": _safe_error_message(error_code)}),
        ]

    response_message = final_response.get("message")
    if isinstance(response_message, str):
        for chunk in _chunk_text(response_message):
            events.append(("token", {"content": chunk}))

    events.append(
        (
            "done",
            {
                "thread_id": thread_id,
                "response": final_response,
                "tool_call_history": tool_history,
            },
        )
    )
    return events


@app.post("/api/agent/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """Streams agent execution events as typed server-sent events."""
    thread_id = request.thread_id or str(uuid4())

    async def event_generator() -> AsyncIterator[str]:
        yield _serialize_sse_event("thinking", {"message": "Analyzing your request..."})

        try:
            base_url = os.getenv("GHOSTFOLIO_API_URL", "http://localhost:3333")
            access_token = os.getenv("GHOSTFOLIO_ACCESS_TOKEN", "test-token")

            async with GhostfolioClient(base_url=base_url, access_token=access_token) as api_client:
                graph = build_graph(api_client=api_client)
                graph_state = await graph.ainvoke(
                    {
                        "thread_id": thread_id,
                        "messages": [{"role": "user", "content": request.message}],
                        "tool_call_history": [],
                    }
                )

            if not isinstance(graph_state, dict):
                raise TypeError("Graph output must be a dictionary state.")

            for event_type, payload in _map_graph_state_to_events(graph_state, thread_id=thread_id):
                yield _serialize_sse_event(event_type, payload)
        except Exception:
            yield _serialize_sse_event(
                "error",
                {
                    "code": "API_ERROR",
                    "message": _safe_error_message("API_ERROR"),
                },
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health() -> dict[str, str]:
    """Returns a liveness health payload for container checks."""
    return {"status": "ok"}
