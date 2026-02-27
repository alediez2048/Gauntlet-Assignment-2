# TICKET-10.2 Regression Recovery Report

## Scope

This closeout addresses the TICKET-10.2 recovery plan goals:

1. Green `agent/tests/integration/`.
2. Lock strict request validation and flat SSE error payload contract.
3. Standardize local UI validation path and precheck.
4. Refresh baseline expectations for transaction counts and allocation fallback behavior.
5. Re-run the key regression matrix and capture evidence.

## Files Updated

- `agent/tests/integration/test_graph_routing.py`
- `agent/tests/integration/test_sse_stream.py`
- `Docs/tickets/ENVIRONMENT-GUIDE.md`
- `Docs/tickets/devlog.md`

## New File

- `Docs/tickets/TICKET-10.2-regression-report.md` (this report)

## What Changed

### 1) Integration regression fixes

- Updated graph test helper to pass LangGraph configurable state (`thread_id`) on every invocation.
- Updated SSE test graph patch signature to match runtime `build_graph(..., synthesizer=...)`.
- Added test harness env setup for SSE tests so `chat()` reaches the patched graph path instead of short-circuiting with `AUTH_FAILED`.

### 2) Contract alignment (strict input + flat SSE error)

- Added explicit integration coverage for whitespace input validation:
  - `test_chat_request_rejects_whitespace_message_with_422`
- Confirmed SSE error payload contract remains flat:
  - `{"code": "...", "message": "..."}`

### 3) Local UI path standardization

- Updated `ENVIRONMENT-GUIDE.md` to define source-based local UI validation as canonical.
- Added mandatory precheck: verify `Open agent chat panel` is visible after login before UI scenario execution.
- Corrected local seed bootstrap command from `GET /api/v1/user` to `POST /api/v1/user`.

### 4) Baseline expectation refresh

- Added current seed baseline values to docs:
  - `BUY=13`, `SELL=5`, `DIVIDEND=3`, `FEE=2`, `INTEREST=2`, `LIABILITY=1`
- Added allocation baseline note for current runtime fallback behavior where holdings can resolve to all `EQUITY`.

## Validation Evidence

### Automated tests (source-based)

```bash
PYTHONPATH=. ./agent/.venv/bin/pytest agent/tests/unit/ -v --tb=short
```

- Result: `45 passed`

```bash
PYTHONPATH=. ./agent/.venv/bin/pytest agent/tests/integration/ -v --tb=short
```

- Result: `14 passed` (includes new `422` validation test)

### Golden path E2E notebook

- Executed all code cells in `agent/tests/e2e/golden_path.ipynb`.
- Result: all assertions passed; `query_count=5`, continuity thread check passed, snapshots captured.

### Section 5/6/10 equivalent reruns

- Section 5 equivalent checks:
  - out-of-domain: pass
  - prompt injection: pass
  - invalid period phrase: pass
  - long message: pass
  - ambiguous query: pass
  - whitespace message: `422` pass
  - missing `message` field: `422` pass
- Section 6 happy-path SSE ordering: pass (`thinking -> tool_call -> tool_result -> token -> done`)
- Section 6 forced error-path SSE: pass (`thinking -> tool_call -> tool_result -> error`) with flat payload:
  - `code: API_ERROR`
  - `message: Received an error from the portfolio service.`
- Section 10 baselines:
  - counts match expected (`BUY=13`, `SELL=5`, `DIVIDEND=3`, `FEE=2`, `INTEREST=2`, `LIABILITY=1`)
  - allocation fallback observed (`asset_classes: [EQUITY]`)
  - tax response mentions expected assets (`AAPL`, `NVDA`, `SPY`)

### Production smoke sanity

- `GET /api/v1/health` (Ghostfolio): `200`
- `GET /health` (agent): `200`
- `POST /api/v1/auth/anonymous`: `201`
- `POST /api/agent/chat`: `200`, terminal SSE event `done`

## Residual Risks / Notes

- Containerized `docker exec gf-agent pytest ...` can run stale test source unless the container image is rebuilt after test-file changes.
- Source-based test execution is now the canonical path for this recovery cycle.
- Python 3.14 warnings from langchain/pydantic compatibility are non-blocking for test pass/fail.

## Final Status

- Integration suite: green.
- Contract: locked to strict input validation + flat SSE error payload.
- Local UI test path: standardized in docs with a hard precheck gate.
- Regression reruns (target matrix): clean.
