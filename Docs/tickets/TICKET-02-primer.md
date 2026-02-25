# TICKET-02 Primer: GhostfolioClient + Auth Module

**For:** New Cursor Agent session  
**Project:** AgentForge — Ghostfolio + AI Agent Integration  
**Date:** Feb 24, 2026  
**Previous work:** TICKET-01 (agent scaffold, Docker Compose, full-stack boot) — see `Docs/tickets/devlog.md`

---

## What Is This Ticket?

TICKET-02 implements the **HTTP client** that every tool will use to talk to Ghostfolio, and the **auth module** that obtains and refreshes the Bearer token. No tools call the API yet; this ticket only builds and tests the client and auth so TICKET-03+ can depend on it.

### Why It Matters

- **Foundation:** All 4 tools (portfolio, transactions, tax, allocation) will receive an injected `GhostfolioClient`; they never instantiate it.
- **Tests:** `MockGhostfolioClient` with fixture JSON lets unit tests run with zero network calls.
- **Auth:** Ghostfolio uses security-token → Bearer flow; the client must authenticate once and refresh on 401.

---

## What Was Already Done (TICKET-01)

- `/agent` directory scaffolded: `main.py`, `auth.py`, `prompts.py`, `clients/`, `tools/`, `graph/`, `tests/`
- Placeholder files: `agent/clients/ghostfolio_client.py`, `agent/clients/mock_client.py`, `agent/auth.py` (all stubs)
- `ToolResult` in `tools/base.py`; `requirements.txt` with httpx, pytest, pytest-asyncio, respx, cachetools
- Full 4-service stack boots with `--env-file .env`; agent health at `http://localhost:8000/health`
- `.env.example` documents `GHOSTFOLIO_API_URL`, `GHOSTFOLIO_ACCESS_TOKEN`, `OPENAI_API_KEY`

---

## What TICKET-02 Must Accomplish

### Goal

Replace the placeholders in `agent/clients/` and `agent/auth.py` with a working HTTP client and Bearer token lifecycle, plus a mock client and fixtures so that tools (TICKET-03+) can be implemented and tested without touching Ghostfolio.

### Deliverables Checklist

#### A. Auth Module (`agent/auth.py`)

- [ ] Read `GHOSTFOLIO_ACCESS_TOKEN` from environment (required at runtime; fail fast if missing).
- [ ] Provide an async function (e.g. `get_bearer_token(base_url: str) -> str`) that:
  1. Calls `POST /api/v1/auth/anonymous` with `{"accessToken": "<GHOSTFOLIO_ACCESS_TOKEN>"}`.
  2. Returns `response.json()["authToken"]` (the Bearer token).
- [ ] Cache the Bearer token (e.g. 60s TTL or until 401); on 401 from any API call, refresh and retry (or expose a refresh function the client can call).
- [ ] Do not log or expose the token; treat as secret.

Reference: `.cursor/rules/ghostfolio-integration.mdc` — auth flow snippet.

#### B. GhostfolioClient (`agent/clients/ghostfolio_client.py`)

- [ ] Class that takes `base_url: str`, `access_token: str`, and optionally an `httpx.AsyncClient` (for tests).
- [ ] On first use (or on init), obtain Bearer token via the auth module and store it.
- [ ] All outbound requests must send `Authorization: Bearer <token>`.
- [ ] On 401 response: refresh token (call auth again), retry the request once; if still 401, surface error (caller/tools will return `ToolResult.fail("AUTH_FAILED")` or similar per `.cursor/rules/error-handling.mdc`).
- [ ] Implement at least these methods (signatures aligned with what tools will need):
  - `get_portfolio_performance(self, time_period: str) -> dict` — `GET /api/v2/portfolio/performance?range=<time_period>`
  - `get_portfolio_details(self) -> dict` — `GET /api/v1/portfolio/details`
  - `get_portfolio_holdings(self) -> dict` — `GET /api/v1/portfolio/holdings`
  - `get_orders(self, date_range: str | None = None) -> dict` — `GET /api/v1/order` (optional `range` param)
- [ ] Use `httpx` async; handle `httpx.TimeoutException` and `httpx.HTTPStatusError` and translate to errors (no raw exceptions to callers).
- [ ] DateRange values: `"1d"`, `"wtd"`, `"mtd"`, `"ytd"`, `"1y"`, `"5y"`, `"max"` (lowercase).

#### C. MockGhostfolioClient (`agent/clients/mock_client.py`)

- [ ] Same **public interface** as `GhostfolioClient` (same method names and signatures).
- [ ] No network calls; return pre-defined data from in-memory dicts or from fixture files.
- [ ] Used by all unit tests for tools; tests must be able to inject this instead of the real client.

#### D. Fixtures (`agent/tests/fixtures/`)

- [ ] Add JSON files that match real Ghostfolio API response shapes (so MockClient and tests can load them):
  - e.g. `performance_ytd.json` (shape of `GET /api/v2/portfolio/performance` response)
  - e.g. `portfolio_details.json`, `orders.json` (shapes for details, holdings, order)
- [ ] Fixtures will be used by MockGhostfolioClient and by unit tests; keep them small and deterministic.

#### E. Unit Tests

- [ ] `agent/tests/unit/test_auth.py` (or under a dedicated auth test module):
  - Test that auth calls `POST /api/v1/auth/anonymous` with the expected body (use respx or httpx mock).
  - Test that returned token is used (e.g. next request has `Authorization: Bearer <token>`).
- [ ] `agent/tests/unit/test_ghostfolio_client.py`:
  - Happy path: client gets Bearer token, then calls e.g. `get_portfolio_performance("ytd")` and returns parsed JSON.
  - 401 triggers refresh and retry (mock: first call 401, after refresh second call 200).
  - Timeout/connection error returns or raises in a way the client converts to a clear error (no uncaught exceptions).
- [ ] Follow TDD: 3+ tests per “unit” (auth lifecycle, client happy path, client error path). See `.cursor/rules/tdd-methodology.mdc`.

#### F. Integration with App (Optional for This Ticket)

- [ ] If desired: in `main.py`, instantiate `GhostfolioClient` with env vars and expose it (e.g. dependency or global) so that later the SSE endpoint can inject it into the graph. Not strictly required until TICKET-08; can be a minimal placeholder.

---

## Important Context

### Files to Modify (All Under `agent/`)

| File | Action |
|------|--------|
| `agent/auth.py` | Replace placeholder with token fetch + cache + refresh |
| `agent/clients/ghostfolio_client.py` | Replace placeholder with httpx client + methods above |
| `agent/clients/mock_client.py` | Replace placeholder with same interface, fixture-backed |
| `agent/tests/fixtures/*.json` | Add at least 1–2 sample response files |
| `agent/tests/unit/test_auth.py` | Create (or add to existing unit layout) |
| `agent/tests/unit/test_ghostfolio_client.py` | Create |
| `agent/tests/conftest.py` | Add fixtures: real client (with test base_url/token), mock client |

### Files You Should NOT Modify

- No Ghostfolio source (`apps/api`, `apps/client`).
- No changes to `docker-compose` or Dockerfile unless required for env (e.g. already have `GHOSTFOLIO_ACCESS_TOKEN` in env_file).

### Cursor Rules to Follow

- `ghostfolio-integration.mdc` — auth flow, endpoints, query params
- `error-handling.mdc` — errors as values; use `AUTH_FAILED`, `API_ERROR`, `API_TIMEOUT` in taxonomy
- `tdd-methodology.mdc` — unit tests with MockGhostfolioClient, 3 tests min per unit
- `agent-patterns.mdc` — tools will receive `api_client`; client interface must be stable
- `python-code-style.mdc` — type hints, docstrings, async/await

### Verified API Details (From TICKET-00 / ghostfolio-integration)

| Endpoint | Auth | Notes |
|----------|------|--------|
| `POST /api/v1/auth/anonymous` | No | Body: `{"accessToken": "<token>"}` → `{"authToken": "<jwt>"}` |
| `GET /api/v2/portfolio/performance` | Bearer | Query: `range` = one of 1d, wtd, mtd, ytd, 1y, 5y, max |
| `GET /api/v1/portfolio/details` | Bearer | |
| `GET /api/v1/portfolio/holdings` | Bearer | |
| `GET /api/v1/order` | Bearer | Optional `range` param |
| `GET /api/v1/health` | No | For connectivity checks |

---

## Definition of Done for TICKET-02

- [ ] `auth.py` implements Bearer token fetch and cache; no token in logs
- [ ] `GhostfolioClient` implements required methods; sends Bearer header; refreshes on 401
- [ ] `MockGhostfolioClient` has same public interface; returns fixture-backed data
- [ ] At least one fixture JSON file added; MockClient uses it
- [ ] Unit tests: auth flow (respx/httpx mock), client happy path, client 401 refresh, client error handling
- [ ] All tests pass: `pytest agent/tests/unit/` (no real network calls)
- [ ] Optional: manual check against live Ghostfolio (full stack up, call client from a small script or test with real base_url)
- [ ] `Docs/tickets/devlog.md` updated with TICKET-02 entry when complete
- [ ] Work committed on a feature branch (e.g. `feature/TICKET-02-ghostfolio-client`)

---

## Estimated Time: 1.5–2 hours

| Task | Estimate |
|------|----------|
| Auth module (fetch, cache, refresh) | 25 min |
| GhostfolioClient (httpx, methods, 401 handling) | 35 min |
| MockGhostfolioClient + fixtures | 20 min |
| Unit tests (auth + client) | 30 min |
| Devlog + branch/commit | 10 min |

---

## After TICKET-02: What Comes Next

- **TICKET-03: Portfolio Performance Analyzer** — Pure function tool that takes `api_client` and `time_period`, calls `client.get_portfolio_performance(time_period)`, and returns `ToolResult`. Unit tests use `MockGhostfolioClient` with performance fixture.
