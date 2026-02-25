# TICKET-03 Primer: Portfolio Performance Analyzer Tool

**For:** New Cursor Agent session  
**Project:** AgentForge — Ghostfolio + AI Agent Integration  
**Date:** Feb 24, 2026  
**Previous work:** TICKET-02 (GhostfolioClient + auth, mock client, fixtures, unit tests) — see `Docs/tickets/devlog.md`

---

## What Is This Ticket?

TICKET-03 implements the first real tool: a pure-function **Portfolio Performance Analyzer** that accepts an injected API client, validates user input, calls Ghostfolio performance endpoint data through the client, and returns a structured `ToolResult`.

### Why It Matters

- **First end-to-end tool contract:** Establishes the exact tool pattern used by all later tools.
- **Validation baseline:** Confirms date-range validation and error-code mapping behavior before graph routing starts.
- **Testing baseline:** Proves the unit-test strategy with `MockGhostfolioClient` and deterministic fixtures.

---

## Branching Rule (Mandatory)

Every ticket must use a dedicated feature branch.

- **Branch for this ticket:** `feature/TICKET-03-portfolio-analyzer`
- **Do not implement new ticket work directly on `main`.**
- **Future naming pattern:** `feature/TICKET-XX-<short-topic>`

---

## What Was Already Done (TICKET-02)

- `agent/auth.py` now handles Ghostfolio token exchange, caching, and refresh helpers.
- `agent/clients/ghostfolio_client.py` now provides:
  - `get_portfolio_performance(time_period)`
  - `get_portfolio_details()`
  - `get_portfolio_holdings()`
  - `get_orders(date_range=None)`
- `GhostfolioClientError` provides structured `error_code` values (`AUTH_FAILED`, `API_TIMEOUT`, `API_ERROR`, `INVALID_TIME_PERIOD`).
- `agent/clients/mock_client.py` is fixture-backed and mirrors the real client interface.
- Fixtures exist under `agent/tests/fixtures/`, including `performance_ytd.json`.
- Unit tests for auth + client pass (`pytest agent/tests/unit/`).

---

## What TICKET-03 Must Accomplish

### Goal

Replace the placeholder in `agent/tools/portfolio_analyzer.py` with a production-style pure async tool function that:

1. Validates input range,
2. Calls `api_client.get_portfolio_performance(time_period)`,
3. Returns `ToolResult.ok(...)` on success,
4. Returns `ToolResult.fail(...)` with taxonomy-aligned error codes on failure.

### Deliverables Checklist

#### A. Tool Implementation (`agent/tools/portfolio_analyzer.py`)

- [ ] Replace placeholder with a public async function, e.g.:
  - `async def analyze_portfolio_performance(api_client, time_period: str = "max") -> ToolResult:`
- [ ] Validate `time_period` against valid ranges:
  - `"1d"`, `"wtd"`, `"mtd"`, `"ytd"`, `"1y"`, `"5y"`, `"max"`
- [ ] On invalid input, return:
  - `ToolResult.fail("INVALID_TIME_PERIOD", time_period=time_period)`
- [ ] On success, call:
  - `await api_client.get_portfolio_performance(time_period)`
  - and return `ToolResult.ok(...)` with useful metadata (for example `source` and `time_period`).
- [ ] Catch `GhostfolioClientError` and map to:
  - `ToolResult.fail(error_code, ...)` using the client's `error_code`
- [ ] Never leak raw exception details to user-facing output.
- [ ] Add full type hints and a concise Google-style docstring.

#### B. Unit Tests (`agent/tests/unit/test_portfolio_analyzer.py`)

- [ ] Add at least 3 tests (TDD rule):
  1. **Happy path**: valid period, mock client returns performance payload, tool returns `success=True`.
  2. **Invalid period**: input rejected before API call, tool returns `INVALID_TIME_PERIOD`.
  3. **Client error path**: client throws `GhostfolioClientError("API_TIMEOUT")` or `("API_ERROR")`, tool returns matching `ToolResult.fail`.
- [ ] Recommended extra tests:
  - `AUTH_FAILED` mapping path.
  - Unexpected exception fallback to `ToolResult.fail("API_ERROR")` without stack trace exposure.

#### C. Fixtures / Test Wiring

- [ ] Reuse existing `agent/tests/fixtures/performance_ytd.json` from TICKET-02.
- [ ] If needed, add one additional performance fixture (for a different range) but keep payload small and deterministic.
- [ ] Reuse `mock_ghostfolio_client` fixture from `agent/tests/conftest.py`.

#### D. Optional Manual Check

- [ ] Optional: run a quick ad-hoc script or small async test against live Ghostfolio to confirm the tool function shape works with real API data.

---

## Important Context

### Files to Modify

| File                                          | Action                                                     |
| --------------------------------------------- | ---------------------------------------------------------- |
| `agent/tools/portfolio_analyzer.py`           | Replace placeholder with tool implementation               |
| `agent/tests/unit/test_portfolio_analyzer.py` | Create unit tests for happy/invalid/error paths            |
| `agent/tests/conftest.py`                     | Optional fixture additions only if needed                  |
| `agent/tests/fixtures/*.json`                 | Optional add-on fixture if current fixture is insufficient |

### Files You Should NOT Modify

- No Ghostfolio app code (`apps/api`, `apps/client`, `libs/*`) for this ticket.
- No Docker/compose changes needed for this ticket.
- No client/auth refactors unless a blocker is discovered.

### Cursor Rules to Follow

- `.cursor/rules/agent-patterns.mdc` — pure tools with injected `api_client`
- `.cursor/rules/error-handling.mdc` — errors as values, taxonomy-aligned codes
- `.cursor/rules/tdd-methodology.mdc` — minimum 3 tests per unit
- `.cursor/rules/ghostfolio-integration.mdc` — endpoint + range conventions
- `.cursor/rules/python-code-style.mdc` — hints/docstrings/import order

### API Contract Used by This Tool

| Method                                              | Endpoint                                                | Notes                         |
| --------------------------------------------------- | ------------------------------------------------------- | ----------------------------- |
| `api_client.get_portfolio_performance(time_period)` | `GET /api/v2/portfolio/performance?range=<time_period>` | Bearer auth handled by client |

---

## Definition of Done for TICKET-03

- [ ] `agent/tools/portfolio_analyzer.py` implemented as pure async function using injected client.
- [ ] Input validation implemented for DateRange values; invalid values return `INVALID_TIME_PERIOD`.
- [ ] Ghostfolio client responses mapped to `ToolResult.ok(...)`.
- [ ] Client errors mapped to `ToolResult.fail(...)` with taxonomy-aligned error code.
- [ ] Unit tests added and passing: `pytest agent/tests/unit/test_portfolio_analyzer.py`
- [ ] Full unit suite still passing: `pytest agent/tests/unit/`
- [ ] `Docs/tickets/devlog.md` updated after completion.
- [ ] Work committed on this ticket branch (`feature/TICKET-03-portfolio-analyzer`) before merge.

---

## Estimated Time: 45–75 minutes

| Task                                 | Estimate  |
| ------------------------------------ | --------- |
| Implement tool function + validation | 20 min    |
| Add/adjust tests                     | 20 min    |
| Run unit tests + fix failures        | 15 min    |
| Devlog + commit on ticket branch     | 10–20 min |

---

## After TICKET-03: What Comes Next

- **TICKET-04: Transaction Categorizer** — build second pure tool on top of the same `api_client` + `ToolResult` pattern.
