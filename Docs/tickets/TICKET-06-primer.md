# TICKET-06 Primer: Asset Allocation Advisor Tool

**For:** New Cursor Agent session
**Project:** AgentForge - Ghostfolio + AI Agent Integration
**Date:** Feb 24, 2026
**Previous work:** TICKET-05 (Capital Gains Tax Estimator implemented, 32 unit tests passing, commit `91748759c` on `feature/TICKET-05-tax-estimator`, pushed to `main`) - see `Docs/tickets/devlog.md`

---

## What Is This Ticket?

TICKET-06 implements the fourth tool: a deterministic **Asset Allocation Advisor** that reads
Ghostfolio's pre-computed allocation data, compares current allocation against a target profile, and
flags concentration risk. Like the first three tools, this is pure logic (no LLM calls).

### Why It Matters

- **Completes all 4 MVP tool contracts:** Portfolio performance, transaction categorization, tax
  estimation, and allocation analysis are the full tool set planned before graph wiring.
- **High demo value:** "Am I diversified?" is a natural query that can return tables/charts and clear
  risk flags.
- **Builds on Ghostfolio strengths:** Ghostfolio already computes `allocationInPercentage` and
  `assetClass`; this ticket focuses on interpretation and structured output.

---

## Branching Rule (Mandatory)

Every ticket must use a dedicated feature branch.

- **Branch for this ticket:** `feature/TICKET-06-allocation-advisor`
- **Do not implement new ticket work directly on `main`.**
- **Future naming pattern:** `feature/TICKET-XX-<short-topic>`

---

## Commit Workflow (Learned in TICKET-04/TICKET-05)

The Husky pre-commit hook (`.husky/pre-commit`) runs Nx lint/format checks for TypeScript/Angular
code. For Python-only ticket work:

1. Stage only ticket files explicitly (never `git add .`):
   - `git add "agent/tools/allocation_advisor.py" "agent/tests/unit/test_allocation_advisor.py" ...`
2. Commit with `--no-verify` to skip irrelevant Nx hooks:
   - `git commit --no-verify -m "TICKET-06: implement asset allocation advisor tool"`
3. Keep commit scope tight to ticket files only.

---

## What Was Already Done (TICKET-02 through TICKET-05)

- `agent/auth.py` handles Ghostfolio token exchange, caching, and refresh helpers.
- `agent/clients/ghostfolio_client.py` provides:
  - `get_portfolio_performance(time_period)`
  - `get_portfolio_details()`
  - `get_portfolio_holdings()`
  - `get_orders(date_range=None)`
- `GhostfolioClientError` exposes structured `error_code` values (`AUTH_FAILED`, `API_TIMEOUT`,
  `API_ERROR`, `INVALID_TIME_PERIOD`).
- `agent/clients/mock_client.py` mirrors the real client interface and is fixture-backed.
- Implemented tools:
  - `agent/tools/portfolio_analyzer.py`
  - `agent/tools/transaction_categorizer.py`
  - `agent/tools/tax_estimator.py`
- `agent/tools/allocation_advisor.py` is still placeholder.
- Current unit suite baseline: **32 tests passing** (`pytest agent/tests/unit/`).

---

## What TICKET-06 Must Accomplish

### Goal

Replace the placeholder in `agent/tools/allocation_advisor.py` with a production-style pure async
tool function that:

1. Validates `target_profile` (one of `"conservative"`, `"balanced"`, `"aggressive"`),
2. Calls `api_client.get_portfolio_details()` (preferred source for allocation metadata),
3. Reads holdings with pre-computed `allocationInPercentage` and `assetClass`,
4. Aggregates current allocation by top-level asset class,
5. Compares current allocation to target profile and computes drift,
6. Flags concentration risk for any single asset allocation above threshold (default: 25%),
7. Returns `ToolResult.ok(...)` with current/target/drift/warnings/suggestions,
8. Maps `GhostfolioClientError` to `ToolResult.fail(error_code, ...)`,
9. Uses taxonomy-aligned failures for invalid profile and empty holdings.

### Target Profiles (Default Mapping)

Use these deterministic targets (sum = 100):

| Profile         | EQUITY | FIXED_INCOME | LIQUIDITY | COMMODITY | REAL_ESTATE | ALTERNATIVE_INVESTMENT |
| --------------- | ------ | ------------ | --------- | --------- | ----------- | ---------------------- |
| `conservative`  | 40     | 50           | 10        | 0         | 0           | 0                      |
| `balanced`      | 60     | 30           | 10        | 0         | 0           | 0                      |
| `aggressive`    | 80     | 15           | 5         | 0         | 0           | 0                      |

### Concentration Rule

- Default threshold: `25.0` percent.
- Warning if any holding's allocation percentage is strictly greater than threshold.

### Deliverables Checklist

#### A. Tool Implementation (`agent/tools/allocation_advisor.py`)

- [ ] Replace placeholder with public async function:
  - `async def advise_asset_allocation(api_client, target_profile: str = "balanced") -> ToolResult:`
- [ ] Validate `target_profile` against allowed values:
  - On invalid: `ToolResult.fail("INVALID_TARGET_PROFILE", target_profile=target_profile)`
- [ ] Fetch data using:
  - `await api_client.get_portfolio_details()`
- [ ] Parse holdings from details payload (`details["holdings"]` map by symbol).
- [ ] If no holdings found:
  - `ToolResult.fail("EMPTY_PORTFOLIO", target_profile=target_profile)`
- [ ] Aggregate current allocation by asset class:
  - `EQUITY`, `FIXED_INCOME`, `LIQUIDITY`, `COMMODITY`, `REAL_ESTATE`,
    `ALTERNATIVE_INVESTMENT`
- [ ] Compute drift per asset class:
  - `drift[class] = current_allocation[class] - target_allocation[class]`
- [ ] Detect concentration warnings:
  - `{"symbol": str, "pct_of_portfolio": float, "threshold": float}`
- [ ] Build short textual rebalancing suggestions from largest positive/negative drifts.
- [ ] Return `ToolResult.ok(...)` with schema below.
- [ ] Catch `GhostfolioClientError` and map to `ToolResult.fail(error_code, ...)`.
- [ ] Never leak raw exception details to user-facing output.
- [ ] Round percentages to 2 decimals.
- [ ] Add full type hints and concise Google-style docstring.

#### B. Output Schema

```python
{
    "target_profile": str,
    "current_allocation": {
        "EQUITY": float,
        "FIXED_INCOME": float,
        "LIQUIDITY": float,
        "COMMODITY": float,
        "REAL_ESTATE": float,
        "ALTERNATIVE_INVESTMENT": float,
    },
    "target_allocation": {
        "EQUITY": float,
        "FIXED_INCOME": float,
        "LIQUIDITY": float,
        "COMMODITY": float,
        "REAL_ESTATE": float,
        "ALTERNATIVE_INVESTMENT": float,
    },
    "drift": {
        "EQUITY": float,
        "FIXED_INCOME": float,
        "LIQUIDITY": float,
        "COMMODITY": float,
        "REAL_ESTATE": float,
        "ALTERNATIVE_INVESTMENT": float,
    },
    "concentration_warnings": [
        {"symbol": str, "pct_of_portfolio": float, "threshold": float}
    ],
    "rebalancing_suggestions": [str],
    "holdings_count": int,
    "disclaimer": "Analysis for informational purposes only. Not financial advice.",
}
```

#### C. Unit Tests (`agent/tests/unit/test_allocation_advisor.py`)

- [ ] **Happy path (allocation drift):**
  - Uses deterministic fixture with mixed asset classes.
  - Asserts exact class-level `current_allocation`, `target_allocation`, and `drift` values.
- [ ] **Concentration warning path:**
  - Includes at least one holding > 25% and asserts warning payload.
- [ ] **Invalid target profile:**
  - Returns `INVALID_TARGET_PROFILE` before API call.
- [ ] **Empty portfolio:**
  - Returns `EMPTY_PORTFOLIO` with structured metadata.
- [ ] **Client error mapping:**
  - `GhostfolioClientError` mapped to matching `ToolResult.fail(error_code)`.
- [ ] **Unexpected exception fallback:**
  - Maps to `ToolResult.fail("API_ERROR")` without leaking internals.

#### D. Test Fixture (`agent/tests/fixtures/portfolio_details_allocation_mix.json`)

Create deterministic holdings with hand-checkable percentages:

- **AAPL (EQUITY):** 45%
- **MSFT (EQUITY):** 20%
- **BND (FIXED_INCOME):** 20%
- **USD Cash proxy (LIQUIDITY):** 10%
- **GLD (COMMODITY):** 5%

Expected totals:
- Current allocation:
  - `EQUITY=65`, `FIXED_INCOME=20`, `LIQUIDITY=10`, `COMMODITY=5`, others `0`
- Balanced target:
  - `EQUITY=60`, `FIXED_INCOME=30`, `LIQUIDITY=10`, others `0`
- Drift:
  - `EQUITY=+5`, `FIXED_INCOME=-10`, `LIQUIDITY=0`, `COMMODITY=+5`
- Concentration warning:
  - AAPL at `45%` crosses `25%` threshold

---

## Important Context

### Files to Modify

| File                                                  | Action                                                        |
| ----------------------------------------------------- | ------------------------------------------------------------- |
| `agent/tools/allocation_advisor.py`                   | Replace placeholder with allocation advisor implementation     |
| `agent/tests/unit/test_allocation_advisor.py`         | Create unit tests for happy/invalid/error/edge paths          |
| `agent/tests/fixtures/portfolio_details_allocation_mix.json` | Add deterministic mixed-allocation fixture             |
| `agent/tests/conftest.py`                             | Optional fixture additions only if needed                     |

### Files You Should NOT Modify

- No Ghostfolio app code (`apps/api`, `apps/client`, `libs/*`) for this ticket.
- No Docker/compose changes needed for this ticket.
- No auth/client refactors unless a blocker is discovered.
- Do not modify existing fixtures (`portfolio_details.json`, `portfolio_holdings.json`,
  `orders.json`, `orders_mixed_types.json`, `orders_tax_scenarios.json`).

### Cursor Rules to Follow

- `.cursor/rules/agent-patterns.mdc` - pure tools with injected `api_client`
- `.cursor/rules/error-handling.mdc` - errors as values, taxonomy-aligned codes
- `.cursor/rules/tdd-methodology.mdc` - minimum 3 tests per unit
- `.cursor/rules/ghostfolio-integration.mdc` - endpoint + type conventions
- `.cursor/rules/python-code-style.mdc` - hints/docstrings/import order

### API Contract Used by This Tool

| Method                              | Endpoint                      | Notes                                         |
| ----------------------------------- | ----------------------------- | --------------------------------------------- |
| `api_client.get_portfolio_details()`| `GET /api/v1/portfolio/details` | Contains holdings with pre-computed allocation fields |

Fields used:
- `holdings.*.symbol`
- `holdings.*.assetClass`
- `holdings.*.allocationInPercentage`
- Optional context: `holdings.*.sectors`, `holdings.*.countries`

---

## Key Complexity Notes

1. **Payload shape:** `portfolio_details["holdings"]` is a dictionary keyed by symbol, not a list.
2. **Pre-computed allocation:** Do not recalculate allocation from prices/quantities when
   `allocationInPercentage` is available.
3. **Allocation normalization:** Ensure all six asset classes exist in output (zero fill missing).
4. **Drift sign convention:** Positive means overweight; negative means underweight versus target.
5. **Sanity checks:** Current allocation should sum to about 100 (+/- 1) due to rounding.
6. **Empty holdings behavior:** Return taxonomy-aligned structured error, not an exception.

---

## Definition of Done for TICKET-06

- [ ] `agent/tools/allocation_advisor.py` implemented as pure async function using injected client.
- [ ] Input validation for `target_profile`; invalid values return structured errors.
- [ ] Current allocation aggregated by asset class from Ghostfolio pre-computed fields.
- [ ] Drift and concentration warnings generated deterministically.
- [ ] All percentage outputs rounded to 2 decimal places.
- [ ] Unit tests with hand-verified expected values passing.
- [ ] Full unit suite still passing: `pytest agent/tests/unit/`
- [ ] `Docs/tickets/devlog.md` updated after completion.
- [ ] Work committed on ticket branch (`feature/TICKET-06-allocation-advisor`) with `--no-verify`.

---

## Estimated Time: 75-120 minutes

| Task                                                  | Estimate |
| ----------------------------------------------------- | -------- |
| Design target profiles + output schema                | 15 min   |
| Implement advisor tool + drift/warning logic          | 30 min   |
| Add fixture + unit tests with exact expected values   | 30 min   |
| Run unit tests + fix failures                         | 15 min   |
| Devlog + branch commit workflow                       | 10 min   |

---

## After TICKET-06: What Comes Next

- **TICKET-07: LangGraph 6-Node Graph + System Prompt** - wire all four tools into router/executor/
  validator/synthesizer flow with deterministic test coverage.
