# TICKET-04 Primer: Transaction Categorizer Tool

**For:** New Cursor Agent session  
**Project:** AgentForge - Ghostfolio + AI Agent Integration  
**Date:** Feb 24, 2026  
**Previous work:** TICKET-03 (Portfolio Analyzer tool implemented, unit tests passing, commit `6e97e3e2d` pushed to `main`) - see `docs/tickets/devlog.md`

---

## What Is This Ticket?

TICKET-04 implements the second real tool: a pure-function **Transaction Categorizer** that accepts an injected API client, validates input, fetches activity data from Ghostfolio orders endpoint data through the client, and returns a structured `ToolResult`.

### Why It Matters

- **MVP-critical second tool:** Portfolio Analyzer + Transaction Categorizer is the minimum useful demo pair.
- **Activity understanding baseline:** Converts raw order activity into grouped categories and portfolio activity summaries.
- **Foundation for TICKET-05:** Tax estimation depends on clean handling of BUY/SELL and supporting activity types.

---

## Branching Rule (Mandatory)

Every ticket must use a dedicated feature branch.

- **Branch for this ticket:** `feature/TICKET-04-transaction-categorizer`
- **Do not implement new ticket work directly on `main`.**
- **Future naming pattern:** `feature/TICKET-XX-<short-topic>`

---

## What Was Already Done (TICKET-02 + TICKET-03)

- `agent/auth.py` handles Ghostfolio token exchange, caching, and refresh helpers.
- `agent/clients/ghostfolio_client.py` provides:
  - `get_portfolio_performance(time_period)`
  - `get_portfolio_details()`
  - `get_portfolio_holdings()`
  - `get_orders(date_range=None)`
- `GhostfolioClientError` exposes structured `error_code` values (`AUTH_FAILED`, `API_TIMEOUT`, `API_ERROR`, `INVALID_TIME_PERIOD`).
- `agent/clients/mock_client.py` mirrors the real client interface and is fixture-backed.
- `agent/tools/portfolio_analyzer.py` is implemented with validation + `ToolResult` mapping and is the reference pattern for this ticket.
- Current unit suite baseline passes (`pytest agent/tests/unit/`) before TICKET-04 work.

---

## What TICKET-04 Must Accomplish

### Goal

Replace the placeholder in `agent/tools/transaction_categorizer.py` with a production-style pure async tool function that:

1. Validates date range input,
2. Calls `api_client.get_orders(date_range=...)`,
3. Categorizes activities by Ghostfolio activity type,
4. Returns `ToolResult.ok(...)` with summary metrics on success,
5. Returns `ToolResult.fail(...)` with taxonomy-aligned error codes on failure.

### Deliverables Checklist

#### A. Tool Implementation (`agent/tools/transaction_categorizer.py`)

- [ ] Replace placeholder with a public async function, e.g.:
  - `async def categorize_transactions(api_client, date_range: str = "max") -> ToolResult:`
- [ ] Validate `date_range` against valid ranges:
  - `"1d"`, `"wtd"`, `"mtd"`, `"ytd"`, `"1y"`, `"5y"`, `"max"`
- [ ] On invalid input, return:
  - `ToolResult.fail("INVALID_TIME_PERIOD", date_range=date_range)`
- [ ] On success, call:
  - `await api_client.get_orders(date_range=date_range)`
- [ ] Parse payload shape (`activities` list, optional `count`) and group into these types:
  - `BUY`, `SELL`, `DIVIDEND`, `FEE`, `INTEREST`, `LIABILITY`
- [ ] Return `ToolResult.ok(...)` with useful output and metadata, including:
  - total transactions
  - by-type counts (all 6 categories represented, even if zero)
  - summary totals (e.g., buys, sells, dividends, interest, fees, liabilities)
  - `source` and `date_range`
- [ ] Catch `GhostfolioClientError` and map to:
  - `ToolResult.fail(error_code, ...)` using the client's `error_code`
- [ ] Never leak raw exception details to user-facing output.
- [ ] Add full type hints and a concise Google-style docstring.

#### B. Unit Tests (`agent/tests/unit/test_transaction_categorizer.py`)

- [ ] Add at least 3 tests (TDD rule):
  1. **Happy path:** mixed activity input, grouped output includes all expected categories and summary totals.
  2. **Invalid range:** input rejected before API call, returns `INVALID_TIME_PERIOD`.
  3. **Client error path:** client throws `GhostfolioClientError("API_TIMEOUT")` or `("API_ERROR")`, tool returns matching `ToolResult.fail`.
- [ ] Recommended extra tests:
  - `AUTH_FAILED` mapping path.
  - Empty activity list returns `success=True` with zeroed summary and empty grouped entries.
  - Unexpected exception fallback to `ToolResult.fail("API_ERROR")` without stack trace exposure.

#### C. Fixtures / Test Wiring

- [ ] Keep existing `agent/tests/fixtures/orders.json` stable for current client tests.
- [ ] Add a dedicated mixed fixture for tool behavior coverage, e.g.:
  - `agent/tests/fixtures/orders_mixed_types.json` with deterministic examples of all 6 activity types.
- [ ] Reuse `mock_ghostfolio_client` fixture from `agent/tests/conftest.py`, or inject `MockGhostfolioClient(orders=...)` directly in tests.
- [ ] Update `agent/tests/conftest.py` only if a shared fixture helper is needed.

#### D. Optional Manual Check

- [ ] Optional: run a quick ad-hoc async check against live Ghostfolio to confirm tool output shape against seeded data.
- [ ] Confirm categorization behavior for available activity types in live data.

---

## Important Context

### Files to Modify

| File                                              | Action                                                     |
| ------------------------------------------------- | ---------------------------------------------------------- |
| `agent/tools/transaction_categorizer.py`          | Replace placeholder with tool implementation               |
| `agent/tests/unit/test_transaction_categorizer.py`| Create unit tests for happy/invalid/error paths            |
| `agent/tests/fixtures/orders_mixed_types.json`    | Add deterministic fixture for 6 activity type coverage     |
| `agent/tests/conftest.py`                         | Optional fixture additions only if needed                  |

### Files You Should NOT Modify

- No Ghostfolio app code (`apps/api`, `apps/client`, `libs/*`) for this ticket.
- No Docker/compose changes needed for this ticket.
- No auth/client refactors unless a blocker is discovered.

### Cursor Rules to Follow

- `.cursor/rules/agent-patterns.mdc` - pure tools with injected `api_client`
- `.cursor/rules/error-handling.mdc` - errors as values, taxonomy-aligned codes
- `.cursor/rules/tdd-methodology.mdc` - minimum 3 tests per unit
- `.cursor/rules/ghostfolio-integration.mdc` - endpoint + type conventions
- `.cursor/rules/python-code-style.mdc` - hints/docstrings/import order

### API Contract Used by This Tool

| Method                                  | Endpoint                                 | Notes                                     |
| --------------------------------------- | ---------------------------------------- | ----------------------------------------- |
| `api_client.get_orders(date_range)`     | `GET /api/v1/order?range=<date_range>`   | Bearer auth handled by client             |

Supported activity types from Ghostfolio enum `Type`:

- `BUY`, `SELL`, `DIVIDEND`, `FEE`, `INTEREST`, `LIABILITY`

---

## Commit Guardrails (Learned in TICKET-03)

Pre-commit hooks in this repo run lint and format checks that can fail on unrelated local files. Before committing ticket work:

1. Run preflight:
   - `git status --short`
   - `npm run affected:lint --base=main --head=HEAD --parallel=2 --quiet`
   - `npm run format:check --uncommitted`
2. If needed, format touched files explicitly (for example):
   - `npx nx format:write --files="Docs/tickets/devlog.md"`
3. Stage only intended ticket files (avoid `git add .` in dirty trees).
4. If unrelated local work exists, temporarily isolate with:
   - `git stash push --keep-index --include-untracked -m "temp-commit"`
   - commit
   - restore stash

---

## Definition of Done for TICKET-04

- [ ] `agent/tools/transaction_categorizer.py` implemented as pure async function using injected client.
- [ ] Input validation implemented for DateRange values; invalid values return `INVALID_TIME_PERIOD`.
- [ ] Activities categorized into all 6 Ghostfolio activity types.
- [ ] Summary metrics computed and returned in `ToolResult.ok(...)`.
- [ ] Client errors mapped to `ToolResult.fail(...)` with taxonomy-aligned error code.
- [ ] Unit tests added and passing: `pytest agent/tests/unit/test_transaction_categorizer.py`
- [ ] Full unit suite still passing: `pytest agent/tests/unit/`
- [ ] `docs/tickets/devlog.md` updated after completion.
- [ ] Work committed on ticket branch (`feature/TICKET-04-transaction-categorizer`) before merge.

---

## Estimated Time: 60-90 minutes

| Task                                        | Estimate  |
| ------------------------------------------- | --------- |
| Implement tool function + aggregation logic | 25 min    |
| Add/adjust tests + fixture                  | 25 min    |
| Run unit tests + fix failures               | 15 min    |
| Devlog + branch commit workflow             | 10-25 min |

---

## After TICKET-04: What Comes Next

- **TICKET-05: Capital Gains Tax Estimator** - build FIFO-based deterministic tax logic on top of `api_client.get_orders(...)` transaction data.
