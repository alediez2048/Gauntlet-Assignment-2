# TICKET-08 Primer: FastAPI SSE Endpoint + Event Mapping

**For:** New Cursor Agent session  
**Project:** AgentForge - Ghostfolio + AI Agent Integration  
**Date:** Feb 24, 2026  
**Previous work:** TICKET-07 completed (LangGraph core + routing integration tests), commit `61f87c99f` on `feature/TICKET-07-langgraph-core`

---

## What Is This Ticket?

TICKET-08 exposes the TICKET-07 LangGraph orchestration over a backend API endpoint:

- Add `POST /api/agent/chat` in the FastAPI service.
- Stream typed SSE events to the frontend (`thinking`, `tool_call`, `tool_result`, `token`, `done`, `error`).
- Map graph/runtime events to a stable SSE contract that the Angular UI can consume.

This is the ticket that turns the graph into a live chat backend.

### Why It Matters

- **Connects backend to UI:** TICKET-09 needs a real stream endpoint to consume.
- **Demo-critical telemetry:** Streaming steps make tool execution explainable during presentation.
- **Operational resilience:** Error event mapping prevents hanging streams and silent failures.
- **Foundation for polish:** Future retries, tracing, and richer frontend states depend on this contract.

---

## Branching Rule (Mandatory)

Every ticket must use a dedicated feature branch.

- **Branch for this ticket:** `feature/TICKET-08-sse-endpoint`
- **Do not implement TICKET-08 directly on `main`.**
- **Do not continue TICKET-08 work on TICKET-07 branch once this primer starts.**

---

## Commit Workflow (Mandatory)

Husky/Nx hooks are TypeScript-heavy and can block Python-only ticket commits.

For this ticket:

1. Stage only ticket files explicitly (never `git add .`).
2. Commit with `--no-verify`.
3. Keep commit scope tight to TICKET-08 files only.

Example:

```bash
git add "agent/main.py" "agent/tests/integration/test_sse_stream.py" "Docs/tickets/devlog.md"
git commit --no-verify -m "TICKET-08: implement SSE chat endpoint and event mapping"
```

---

## What Is Already Done (Carry-Forward Context)

- Ghostfolio auth helpers exist: `agent/auth.py`
- API client exists: `agent/clients/ghostfolio_client.py`
- Deterministic tools exist and are tested:
  - `analyze_portfolio_performance`
  - `categorize_transactions`
  - `estimate_capital_gains_tax`
  - `advise_asset_allocation`
- LangGraph 6-node orchestration exists:
  - `agent/graph/state.py`
  - `agent/graph/nodes.py`
  - `agent/graph/graph.py`
- Prompt/routing constants exist: `agent/prompts.py`
- Integration routing tests exist: `agent/tests/integration/test_graph_routing.py` (6 passing)
- Current FastAPI app is minimal (`agent/main.py`) and still needs chat/SSE implementation.

---

## What TICKET-08 Must Accomplish

### Goal

Implement a production-style streaming endpoint that:

1. Accepts chat requests at `POST /api/agent/chat`.
2. Executes the compiled graph with injected dependencies.
3. Emits typed SSE events in a stable frontend-facing format.
4. Handles graph/tool/runtime failures with a final `error` event (no stack traces leaked).
5. Closes streams cleanly with a terminal `done` or `error` event.

### Required SSE Event Contract

Events must use this event name set:

- `thinking`
- `tool_call`
- `tool_result`
- `token`
- `done`
- `error`

And follow FastAPI SSE formatting:

```text
event: <event_type>
data: <json_payload>

```

### Target Endpoint

- `POST /api/agent/chat`
- Content type: JSON
- Minimum request shape:
  - `message: str`
  - `thread_id: str` (or generated fallback if absent)
- Response:
  - `StreamingResponse(..., media_type="text/event-stream")`

---

## Deliverables Checklist

### A. API Models + Endpoint (`agent/main.py`)

- [ ] Add request model for chat payload.
- [ ] Add `POST /api/agent/chat`.
- [ ] Keep existing `GET /health`.
- [ ] Ensure CORS is correct for local Ghostfolio/Angular origins.

### B. Graph Invocation + Dependency Injection

- [ ] Build graph instance with injected API client/router dependency.
- [ ] Convert request input into initial `AgentState` (`messages`, etc.).
- [ ] Invoke graph in a stream-friendly way suitable for SSE emission.

### C. SSE Mapping Layer

- [ ] Emit `thinking` first.
- [ ] Emit `tool_call` when a tool is selected/executed.
- [ ] Emit `tool_result` when tool execution completes.
- [ ] Emit `token` for incremental response chunks if available (or deterministic chunking fallback).
- [ ] Emit terminal `done` with final response payload.
- [ ] Emit terminal `error` on failures, then close stream.

### D. Error Handling

- [ ] Do not expose stack traces or raw internal exceptions.
- [ ] Map expected failures to user-safe messages.
- [ ] Guarantee stream termination (`done` or `error` always sent).

### E. Tests (No Live LLM Required)

- [ ] Add integration tests for event order and event payload shape.
- [ ] Add test that verifies `thinking` is first.
- [ ] Add test that verifies `done` is last on success.
- [ ] Add failure-path test that verifies `error` event is emitted and stream closes.
- [ ] Keep tests deterministic (mock graph/runtime outputs).

---

## Suggested Event Payload Shapes

Use stable, minimal payloads:

- `thinking`: `{"message":"Analyzing your request..."}`
- `tool_call`: `{"tool":"analyze_portfolio_performance","args":{"time_period":"ytd"}}`
- `tool_result`: `{"tool":"analyze_portfolio_performance","success":true}`
- `token`: `{"content":"..."}`
- `done`: `{"response":{...final_response...},"tool_call_history":[...]}`
- `error`: `{"code":"API_ERROR","message":"Received an error from the portfolio service."}`

---

## Files to Modify

| File | Action |
| --- | --- |
| `agent/main.py` | Implement chat request model + SSE endpoint |
| `agent/graph/graph.py` | Optional minor helpers for stream integration (only if needed) |
| `agent/tests/integration/test_sse_stream.py` | New SSE integration tests |
| `agent/tests/conftest.py` | Optional reusable SSE fixtures/helpers |
| `Docs/tickets/devlog.md` | Update TICKET-08 entry after completion |

## Files You Should NOT Modify

- No Ghostfolio app code (`apps/api`, `apps/client`, `libs/*`) in this ticket.
- No changes to tool math unless a blocker bug is discovered.
- Avoid Docker/compose scope creep unless endpoint cannot be validated without tiny fix.

---

## Key Complexity Notes

1. **Event ordering:** Frontend UX depends on deterministic order (`thinking` before anything else).
2. **Stream lifecycle:** Never leave a stream hanging on exceptions.
3. **State/event bridge:** Map graph state transitions to SSE events without leaking internals.
4. **Token streaming realism:** If true incremental LLM tokens are unavailable now, use a deterministic fallback and document it.
5. **Backpressure simplicity:** Keep implementation straightforward for MVP; defer advanced buffering/retry logic.

---

## Definition of Done for TICKET-08

- [ ] `POST /api/agent/chat` implemented in FastAPI.
- [ ] SSE stream returns typed events in required format.
- [ ] `thinking` emitted first.
- [ ] `done` emitted last on success.
- [ ] `error` emitted on failure and stream closes cleanly.
- [ ] New SSE integration tests pass locally (no live LLM dependency).
- [ ] Existing unit/integration suites remain green.
- [ ] `Docs/tickets/devlog.md` updated with status, files, tests, and totals.
- [ ] Work committed on `feature/TICKET-08-sse-endpoint` using `--no-verify`.

---

## Estimated Time: 120-180 minutes

| Task | Estimate |
| --- | --- |
| Chat endpoint + request model | 20 min |
| Graph invocation + dependency wiring | 25 min |
| SSE event mapper implementation | 35 min |
| Error/termination handling | 20 min |
| SSE integration tests | 35 min |
| Devlog + commit workflow | 10 min |

---

## After TICKET-08: What Comes Next

- **TICKET-09: Angular Agent UI (FAB + chat panel)**  
  Consume the SSE stream in frontend `AgentService` and render progressive updates.
