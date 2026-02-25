# TICKET-09 Primer: Angular Agent UI - FAB + Chat Panel

**For:** New Cursor Agent session  
**Project:** AgentForge - Ghostfolio + AI Agent Integration  
**Date:** Feb 24, 2026  
**Previous work:** TICKET-08 completed (FastAPI SSE endpoint + event mapping + runtime/docker debugging), commit `bf23913f4` on `feature/TICKET-08-sse-endpoint`

---

## What Is This Ticket?

TICKET-09 is the first end-user UI milestone for the agent:

- Build a floating action button (FAB) in Ghostfolio.
- Open a chat panel overlay from that FAB.
- Stream and render typed SSE events from `POST /api/agent/chat`.
- Present deterministic, readable chat blocks (`thinking`, `tool_call`, `tool_result`, `token`, `done`, `error`).

This ticket turns the backend stream built in TICKET-08 into a usable product surface.

### Why It Matters

- **User-facing integration:** The backend works, but users currently cannot interact with it in-app.
- **Demo readiness:** Interview/demo flow requires a visible chat UX in Ghostfolio.
- **Event transparency:** Tool telemetry and progressive output are core differentiators of this project.
- **Foundation for TICKET-10/TICKET-11:** Docker E2E and edge-case testing depend on a real UI entrypoint.

---

## Runtime Reality from TICKET-08 (Critical Context)

Use this matrix to avoid the confusion we just debugged:

| Mode | Ghostfolio UI | Ghostfolio API | Agent API | Use Case |
| --- | --- | --- | --- | --- |
| **Hybrid Dev (recommended for TICKET-09)** | `https://localhost:4200/en/home` | `http://localhost:3333` (local Node API behind Angular proxy) | `http://localhost:8000` (Docker `agent-dev` overlay) | Frontend development + live SSE |
| **Full Docker Stack** | `http://localhost:3333/en` | `http://localhost:3333` | `http://localhost:8000` | Final integration checks |

Important notes:

- In hybrid dev mode, treat `https://localhost:4200/en/home` as source-of-truth UI.
- `http://localhost:8000` returning `{"detail":"Not Found"}` is expected at root (`/`).
- Agent health/docs live at:
  - `http://localhost:8000/health`
  - `http://localhost:8000/docs`
- Do not run hybrid mode and full-stack mode simultaneously unless intentionally debugging port ownership.

---

## Branching Rule (Mandatory)

Every ticket must use a dedicated feature branch.

- **Branch for this ticket:** `feature/TICKET-09-angular-agent-ui`
- **Do not implement TICKET-09 on `main`.**
- **Do not continue TICKET-09 on `feature/TICKET-08-sse-endpoint`.**

---

## Commit Workflow (Mandatory)

Local Husky/Nx hooks have intermittently failed in this workspace (plugin worker startup).  
For this ticket, follow the established local workflow:

1. Run targeted checks manually first (lint/tests relevant to changed files).
2. Stage only TICKET-09 files explicitly (never `git add .`).
3. Commit with `--no-verify`.

Example:

```bash
git add "apps/client/src/app/app.routes.ts" \
        "apps/client/src/app/app.component.ts" \
        "apps/client/src/app/app.component.html" \
        "apps/client/src/app/pages/agent/..."
git commit --no-verify -m "TICKET-09: implement Angular agent FAB and streaming chat panel"
```

---

## What Is Already Done (Carry-Forward Context)

- Backend SSE endpoint is live: `POST /api/agent/chat` in `agent/main.py`.
- SSE event contract is implemented and tested:
  - `thinking`, `tool_call`, `tool_result`, `token`, `done`, `error`
- Deterministic SSE integration tests exist:
  - `agent/tests/integration/test_sse_stream.py`
- LangSmith tracing is configured and verified with live runs.
- Dev Docker overlay exists for agent-to-host Ghostfolio connectivity:
  - `docker/docker-compose.agent-dev.yml`
- Runtime debugging confirmed successful end-to-end stream after alignment:
  - `tool_result.success=true` -> `token` -> terminal `done`.

---

## What TICKET-09 Must Accomplish

### Goal

Implement a production-style Angular chat experience that:

1. Adds a floating agent entrypoint (`gf-agent-fab`) to the app shell.
2. Opens a chat panel overlay with message input/output.
3. Calls the FastAPI SSE endpoint via `fetch` + stream reader (POST-based SSE).
4. Parses and renders typed events progressively.
5. Handles error/abort states cleanly without freezing UI.
6. Keeps blast radius minimal (new files preferred; only approved existing files touched).

### Backend Contract to Consume

`POST http://localhost:8000/api/agent/chat`

Request payload:

```json
{
  "message": "How is my portfolio doing ytd?",
  "thread_id": "optional-string"
}
```

SSE event names:

- `thinking`
- `tool_call`
- `tool_result`
- `token`
- `done`
- `error`

---

## Deliverables Checklist

### A. Feature Scaffolding (New Angular Files)

- [ ] Create `apps/client/src/app/pages/agent/` feature folder.
- [ ] Use standalone components only (no NgModules).
- [ ] Use naming convention:
  - class prefix `Gf`
  - selector prefix `gf-agent-`

### B. App Shell Integration (Only Approved Existing Files)

- [ ] `apps/client/src/app/app.routes.ts`: add one lazy route for agent page routes.
- [ ] `apps/client/src/app/app.component.ts`: add FAB component to `imports`.
- [ ] `apps/client/src/app/app.component.html`: add FAB overlay tag.

### C. Agent Service (SSE Client)

- [ ] Add `AgentService` with `@Injectable({ providedIn: 'root' })`.
- [ ] Implement POST-based SSE consumption using `fetch` + `getReader()`.
- [ ] Parse `event:` / `data:` frames safely across chunk boundaries.
- [ ] Emit typed UI events/state updates.
- [ ] Support `thread_id` continuity between turns.
- [ ] Handle stream termination and network failures robustly.

### D. Chat UI Components

- [ ] FAB component toggles panel open/closed.
- [ ] Chat panel shows:
  - user messages
  - assistant progressive output (token accumulation)
  - tool telemetry blocks
  - final/done state
  - error state
- [ ] Input UX:
  - Enter to send
  - disable while stream active
  - clear input on successful submit

### E. Block Renderers

- [ ] Render `thinking` as loading block.
- [ ] Render `tool_call` with tool name + args summary.
- [ ] Render `tool_result` with success/failure styling.
- [ ] Stream `token` chunks into in-progress assistant message.
- [ ] Finalize message on `done`.
- [ ] Render safe error message on `error`.

### F. Frontend Runtime Config for Agent Endpoint

- [ ] Add a dedicated agent endpoint config mechanism in the new feature (no hard-coded scatter).
- [ ] Keep this ticket scoped to frontend-only configuration where possible.
- [ ] Do not introduce broad environment refactors unless needed for unblock.

### G. Tests + Verification

- [ ] Add unit tests for SSE frame parsing and state reduction logic.
- [ ] Add component tests for basic panel open/close and send flow.
- [ ] Run client lint/tests for changed files.
- [ ] Perform manual runtime verification in hybrid dev mode.

---

## Suggested File Layout (TICKET-09)

```text
apps/client/src/app/pages/agent/
├── agent-page.routes.ts
├── agent-page.component.ts                # optional route shell
├── components/
│   ├── agent-fab/
│   │   ├── agent-fab.component.ts
│   │   ├── agent-fab.component.html
│   │   └── agent-fab.component.scss
│   ├── agent-chat-panel/
│   │   ├── agent-chat-panel.component.ts
│   │   ├── agent-chat-panel.component.html
│   │   └── agent-chat-panel.component.scss
│   └── event-blocks/
│       ├── thinking-block.component.ts
│       ├── tool-call-block.component.ts
│       ├── tool-result-block.component.ts
│       └── error-block.component.ts
├── services/
│   └── agent.service.ts
└── models/
    └── agent-chat.models.ts
```

---

## Event-to-UI Mapping Reference

Use a deterministic UI reducer/state transition map:

| SSE Event | UI Effect |
| --- | --- |
| `thinking` | Append/activate a transient "Analyzing..." status block |
| `tool_call` | Append telemetry block with selected tool + args |
| `tool_result` | Update telemetry result status (success/error) |
| `token` | Append chunk to current assistant draft message |
| `done` | Finalize assistant message + attach response metadata |
| `error` | Finalize turn as failure with safe error copy |

---

## Files to Modify

| File | Action |
| --- | --- |
| `apps/client/src/app/app.routes.ts` | Add lazy route entry for agent page routes |
| `apps/client/src/app/app.component.ts` | Register FAB component in standalone imports |
| `apps/client/src/app/app.component.html` | Insert FAB component tag |
| `apps/client/src/app/pages/agent/**` | New agent feature, components, service, models, tests |
| `Docs/tickets/devlog.md` | Update TICKET-09 entry after completion |

## Files You Should NOT Modify (Unless Blocked)

- `apps/api/**` backend NestJS code (not needed for this ticket)
- `agent/**` FastAPI/LangGraph backend (already complete for TICKET-09 scope)
- Docker files (unless a real blocker appears)
- Broad Ghostfolio refactors outside approved shell touchpoints

---

## Constraints from Project Rules

- Standalone components only (no NgModules).
- Selector prefix must be `gf-agent-`.
- Keep existing-file edits minimal:
  - `app.routes.ts`
  - `app.component.ts`
  - `app.component.html`
- Prefer new files for all agent UI logic.

---

## Manual Verification Runbook (Hybrid Dev)

1. Run Ghostfolio frontend/backend in local dev mode (`https://localhost:4200/en/home`).
2. Run agent via Docker dev overlay (`docker/docker-compose.agent-dev.yml`).
3. Confirm agent health: `http://localhost:8000/health`.
4. Open Ghostfolio at `https://localhost:4200/en/home`.
5. Open FAB -> send a query.
6. Confirm you see ordered stream behavior:
   - thinking -> tool_call -> tool_result -> token(s) -> done (or error).
7. Confirm a matching run appears in LangSmith.

---

## Key Complexity Notes

1. **POST + SSE parsing:** `EventSource` is not usable for this flow; parse streamed POST response chunks carefully.
2. **Chunk boundaries:** SSE frames can split across network chunks; parser must buffer incomplete frames.
3. **Progressive UX:** Token rendering should be incremental but deterministic and flicker-free.
4. **State hygiene:** Ensure cancellation/new prompt behavior does not leak stale tool states.
5. **Mode confusion:** Validate against hybrid dev mode defaults to avoid port/instance mismatches.

---

## Definition of Done for TICKET-09

- [ ] FAB is visible and opens/closes a chat panel in Ghostfolio UI.
- [ ] Chat panel can send user message to agent endpoint.
- [ ] SSE stream is parsed and rendered with typed blocks/events.
- [ ] Progressive token output appears before terminal event.
- [ ] Error path is rendered safely and does not lock UI.
- [ ] Existing app shell remains stable after integration.
- [ ] New frontend tests and lint checks pass for changed scope.
- [ ] Manual hybrid-mode verification is successful.
- [ ] LangSmith shows runs initiated from UI chat interactions.
- [ ] `Docs/tickets/devlog.md` updated after completion.
- [ ] Work committed on `feature/TICKET-09-angular-agent-ui` using local commit policy.

---

## Estimated Time: 180-300 minutes

| Task | Estimate |
| --- | --- |
| Scaffold agent feature components/services/models | 45 min |
| Implement SSE service parser + stream reducer | 60 min |
| Build FAB/panel UI and event block rendering | 60 min |
| Wire app shell + route integration | 20 min |
| Add tests + run lint/test checks | 40 min |
| Manual verification + devlog update | 20 min |

---

## After TICKET-09: What Comes Next

- **TICKET-10: Docker Compose + Seed Data + E2E**  
  Validate complete stack behavior with reproducible startup, seeded portfolio data, and demo-ready flow.
