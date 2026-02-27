"""FastAPI application entrypoint for AgentForge."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import dotenv_values

# Load select keys from the repo-root .env.  GHOSTFOLIO_API_URL is
# intentionally excluded because .env contains the Docker-internal hostname
# (http://ghostfolio:3333) while local dev needs http://localhost:3333
# (the code default).  On Railway, env vars are set directly on the service.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOTENV_KEYS_TO_LOAD = {"OPENAI_API_KEY", "LANGSMITH_TRACING", "LANGSMITH_ENDPOINT",
                        "LANGSMITH_API_KEY", "LANGSMITH_PROJECT"}
_dotenv_vals = dotenv_values(_REPO_ROOT / ".env")
for _key in _DOTENV_KEYS_TO_LOAD:
    _val = _dotenv_vals.get(_key)
    if _val:
        os.environ[_key] = _val

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from agent.clients.ghostfolio_client import GhostfolioClient, GhostfolioClientError
from agent.graph.graph import build_graph
from agent.prompts import ROUTING_FEW_SHOT_EXAMPLES, ROUTING_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

try:
    from langchain_openai import ChatOpenAI as _ChatOpenAI
except ModuleNotFoundError:
    _ChatOpenAI = None


def _build_synthesizer_callable() -> Any | None:
    """Builds an async callable that uses GPT-4o to narrate tool results."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or _ChatOpenAI is None:
        return None

    llm = _ChatOpenAI(model="gpt-4o", temperature=0.3, max_tokens=512)

    async def _synthesize(system_prompt: str, user_content: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        response = await llm.ainvoke(messages)
        text = response.content if hasattr(response, "content") else str(response)
        return text.strip() if isinstance(text, str) else str(text).strip()

    return _synthesize


def _build_router_callable() -> Any | None:
    """Builds an async LLM-backed router using GPT-4o function calling."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or _ChatOpenAI is None:
        return None

    llm = _ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=256)

    # Build few-shot messages from the prompt examples
    few_shot_messages: list[dict[str, str]] = []
    for example in ROUTING_FEW_SHOT_EXAMPLES:
        few_shot_messages.append({"role": "user", "content": example["user"]})
        few_shot_messages.append(
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "route": example["route"],
                        "tool_name": example["tool_name"],
                        "tool_args": json.loads(example["tool_args"])
                        if isinstance(example["tool_args"], str)
                        else example["tool_args"],
                        "reason": "few_shot_example",
                    }
                ),
            }
        )

    async def _route(user_query: str, messages: list[Any]) -> dict[str, Any]:
        llm_messages = [
            {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{ROUTING_PROMPT}"},
            *few_shot_messages,
            {"role": "user", "content": user_query},
        ]
        response = await llm.ainvoke(llm_messages)
        text = response.content if hasattr(response, "content") else str(response)
        text = text.strip() if isinstance(text, str) else str(text).strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
        if text.endswith("```"):
            text = "\n".join(text.split("\n")[:-1])
        text = text.strip()

        return json.loads(text)

    return _route


_DEFAULT_CORS_ORIGINS: list[str] = [
    "http://localhost:3333",
    "https://localhost:3333",
    "http://localhost:4200",
    "https://localhost:4200",
]


def _resolve_cors_origins() -> list[str]:
    """Returns de-duplicated CORS origins from defaults and env overrides."""
    configured_origins = os.getenv("AGENT_CORS_ORIGINS", "")
    raw_origins = [*_DEFAULT_CORS_ORIGINS, *configured_origins.split(",")]

    resolved_origins: list[str] = []
    for raw_origin in raw_origins:
        origin = raw_origin.strip().rstrip("/")
        if origin and origin not in resolved_origins:
            resolved_origins.append(origin)

    return resolved_origins


_BUILD_VERSION = "synth-v2"

app = FastAPI(title="AgentForge", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

_SAFE_ERROR_MESSAGES: dict[str, str] = {
    "INVALID_TIME_PERIOD": "Please use a valid period such as ytd, 1y, or max.",
    "INVALID_TAX_YEAR": "Tax year must be between 2020 and the current year.",
    "API_TIMEOUT": "Having trouble reaching portfolio data. Is Ghostfolio running?",
    "API_ERROR": "Received an error from the portfolio service.",
    "EMPTY_PORTFOLIO": (
        "No holdings found. Use the 'Load Sample Portfolio' button on the home page,"
        " or add your own investments in Ghostfolio."
    ),
    "AUTH_REQUIRED": "Please sign in or create an account to get portfolio insights.",
    "AUTH_FAILED": "Your session has expired. Please sign in again.",
}
_THREAD_STATE_CACHE: dict[str, dict[str, Any]] = {}


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
    history_offset: int = 0,
) -> list[tuple[str, dict[str, Any]]]:
    """Maps graph output state to frontend-facing SSE events."""
    events: list[tuple[str, dict[str, Any]]] = []
    tool_history = _coerce_tool_call_history(state.get("tool_call_history"))
    emitted_tool_history = (
        tool_history[history_offset:]
        if history_offset > 0 and history_offset <= len(tool_history)
        else tool_history
    )

    for record in emitted_tool_history:
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


def _extract_bearer_token(auth_header: str | None) -> str | None:
    """Returns the Bearer token from an Authorization header, or None."""
    if not auth_header or not isinstance(auth_header, str):
        return None
    parts = auth_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        return None
    return parts[1]


@app.post("/api/agent/chat")
async def chat(request: ChatRequest, raw_request: Request) -> StreamingResponse:
    """Streams agent execution events as typed server-sent events.

    Requires an Authorization: Bearer <jwt> header with the logged-in user's
    Ghostfolio JWT. Returns AUTH_REQUIRED if no token is provided.
    """
    thread_id = request.thread_id or str(uuid4())

    async def event_generator() -> AsyncIterator[str]:
        yield _serialize_sse_event("thinking", {"message": "Analyzing your request..."})

        try:
            base_url = os.getenv("GHOSTFOLIO_API_URL", "http://localhost:3333")
            auth_header = raw_request.headers.get("Authorization")
            user_bearer = _extract_bearer_token(auth_header)

            if user_bearer:
                logger.info("chat: using request Bearer token (caller identity)")
                api_client = GhostfolioClient(
                    base_url, access_token="", bearer_token=user_bearer
                )
            else:
                logger.info("chat: no Bearer token provided; returning auth-required")
                yield _serialize_sse_event(
                    "error",
                    {"code": "AUTH_REQUIRED", "message": _safe_error_message("AUTH_REQUIRED")},
                )
                return

            prior_state = _THREAD_STATE_CACHE.get(thread_id, {})
            prior_messages = prior_state.get("messages")
            prior_tool_history = _coerce_tool_call_history(prior_state.get("tool_call_history"))
            prior_history_len = len(prior_tool_history)

            graph_input_messages: list[Any] = []
            if isinstance(prior_messages, list):
                graph_input_messages.extend(prior_messages)
            graph_input_messages.append({"role": "user", "content": request.message})

            graph_input: dict[str, Any] = {"messages": graph_input_messages}
            if prior_tool_history:
                graph_input["tool_call_history"] = prior_tool_history

            async with api_client:
                router = _build_router_callable()
                synthesizer = _build_synthesizer_callable()
                graph = build_graph(api_client=api_client, router=router, synthesizer=synthesizer)
                graph_state = await graph.ainvoke(
                    graph_input,
                    config={"configurable": {"thread_id": thread_id}},
                )

            if not isinstance(graph_state, dict):
                raise TypeError("Graph output must be a dictionary state.")

            _THREAD_STATE_CACHE[thread_id] = {
                "messages": graph_state.get("messages", graph_input_messages),
                "tool_call_history": _coerce_tool_call_history(graph_state.get("tool_call_history")),
            }

            for event_type, payload in _map_graph_state_to_events(
                graph_state,
                thread_id=thread_id,
                history_offset=prior_history_len,
            ):
                yield _serialize_sse_event(event_type, payload)
        except GhostfolioClientError as err:
            code = err.error_code
            logger.warning(
                "chat: GhostfolioClientError code=%s status=%s detail=%s",
                code,
                err.status,
                err.detail,
            )
            yield _serialize_sse_event(
                "error",
                {"code": code, "message": _safe_error_message(code)},
            )
        except Exception:
            logger.exception("chat: unexpected error")
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
    return {"status": "ok", "version": _BUILD_VERSION}
