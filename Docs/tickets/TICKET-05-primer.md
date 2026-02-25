# TICKET-05 Primer: Capital Gains Tax Estimator Tool

**For:** New Cursor Agent session
**Project:** AgentForge - Ghostfolio + AI Agent Integration
**Date:** Feb 24, 2026
**Previous work:** TICKET-04 (Transaction Categorizer implemented, 22 unit tests passing, commit `7cbbe580e` on `feature/TICKET-04-transaction-categorizer`) - see `docs/tickets/devlog.md`

---

## What Is This Ticket?

TICKET-05 implements the third tool: a deterministic **Capital Gains Tax Estimator** that uses FIFO (First-In-First-Out) cost-basis tracking to calculate estimated tax liability from BUY/SELL transaction pairs. This is the most algorithmically complex tool in the agent — it contains no LLM calls, only pure math.

### Why It Matters

- **Demonstrates deterministic non-LLM logic:** Unlike portfolio analysis or categorization, tax estimation is a self-contained algorithm that must produce exact, hand-verifiable results.
- **FIFO is the standard:** Most US brokerages default to FIFO cost basis, making this the most useful default for users.
- **Foundation for demo impact:** "What are my tax implications?" is a high-value demo query that showcases the agent doing real financial computation.

---

## Branching Rule (Mandatory)

Every ticket must use a dedicated feature branch.

- **Branch for this ticket:** `feature/TICKET-05-tax-estimator`
- **Do not implement new ticket work directly on `main`.**
- **Future naming pattern:** `feature/TICKET-XX-<short-topic>`

---

## Commit Workflow (Learned in TICKET-04)

The Husky pre-commit hook (`.husky/pre-commit`) runs Nx lint and format checks that only apply to TypeScript/Angular files. For Python-only ticket work:

1. Stage only ticket files explicitly (never `git add .`):
   - `git add "agent/tools/tax_estimator.py" "agent/tests/unit/test_tax_estimator.py" ...`
2. Commit with `--no-verify` to skip the irrelevant Nx hooks:
   - `git commit --no-verify -m "TICKET-05: implement capital gains tax estimator tool"`
3. No stash dance, no preflight, no format:check needed for Python-only changes.

---

## What Was Already Done (TICKET-02 through TICKET-04)

- `agent/auth.py` handles Ghostfolio token exchange, caching, and refresh helpers.
- `agent/clients/ghostfolio_client.py` provides:
  - `get_portfolio_performance(time_period)`
  - `get_portfolio_details()`
  - `get_portfolio_holdings()`
  - `get_orders(date_range=None)`
- `GhostfolioClientError` exposes structured `error_code` values (`AUTH_FAILED`, `API_TIMEOUT`, `API_ERROR`, `INVALID_TIME_PERIOD`).
- `agent/clients/mock_client.py` mirrors the real client interface and is fixture-backed.
- `agent/tools/portfolio_analyzer.py` — validates range, calls client, returns `ToolResult`.
- `agent/tools/transaction_categorizer.py` — validates range, fetches orders, groups by 6 activity types, computes summary totals.
- `agent/tools/base.py` — `ToolResult` dataclass with `ok`/`fail` class methods.
- `agent/tests/fixtures/orders_mixed_types.json` — fixture with all 6 activity types (1 of each).
- Current unit suite baseline: **22 tests passing** (`pytest agent/tests/unit/`).

---

## What TICKET-05 Must Accomplish

### Goal

Replace the placeholder in `agent/tools/tax_estimator.py` with a production-style pure async tool function that:

1. Validates `tax_year` (between 2020 and current year),
2. Validates `income_bracket` (one of `"low"`, `"middle"`, `"high"`),
3. Calls `api_client.get_orders()` to fetch all transactions,
4. Filters for only `BUY` and `SELL` activity types (ignores DIVIDEND, FEE, INTEREST, LIABILITY),
5. Implements FIFO cost-basis lot matching algorithm,
6. Classifies each realized gain/loss as short-term (<=365 days) or long-term (>365 days),
7. Applies simplified tax rates based on `income_bracket`,
8. Returns `ToolResult.ok(...)` with per-asset breakdown and combined liability,
9. Returns `ToolResult.fail(...)` with taxonomy-aligned error codes on failure.

### FIFO Algorithm (Core Logic)

```
1. Group all activities by symbol
2. For each symbol, separate BUY and SELL lists
3. Sort BUYs ascending by date (oldest first = FIFO order)
4. For each SELL (in date order):
   a. Consume oldest available BUY lots until SELL quantity is fulfilled
   b. For each consumed lot:
      - cost_basis = lot.unitPrice * consumed_quantity
      - proceeds = sell.unitPrice * consumed_quantity
      - gain_loss = proceeds - cost_basis
      - holding_days = (sell.date - buy.date).days
      - If holding_days > 365 → long-term, else → short-term
   c. If a BUY lot is partially consumed, keep the remainder for the next SELL
5. Aggregate short-term and long-term gains/losses separately
6. Apply tax rates per income_bracket
```

### Simplified Tax Rates

| Bracket  | Short-Term Rate | Long-Term Rate |
| -------- | --------------- | -------------- |
| `low`    | 22%             | 0%             |
| `middle` | 24%             | 15%            |
| `high`   | 24%             | 20%            |

### Deliverables Checklist

#### A. Tool Implementation (`agent/tools/tax_estimator.py`)

- [ ] Replace placeholder with a public async function:
  - `async def estimate_capital_gains_tax(api_client, tax_year: int = 2025, income_bracket: str = "middle") -> ToolResult:`
- [ ] Validate `tax_year` between 2020 and `datetime.now().year`:
  - On invalid: `ToolResult.fail("INVALID_TAX_YEAR", tax_year=tax_year)`
- [ ] Validate `income_bracket` against `{"low", "middle", "high"}`:
  - On invalid: `ToolResult.fail("INVALID_INCOME_BRACKET", income_bracket=income_bracket)`
- [ ] Call `await api_client.get_orders()` (fetch all, filter by year in tool logic).
- [ ] Filter activities to only `BUY` and `SELL` types.
- [ ] Filter SELL activities to only those within `tax_year`.
- [ ] Implement FIFO lot matching algorithm (see above).
- [ ] Classify each realized gain/loss as short-term or long-term.
- [ ] Apply tax rates from the bracket table.
- [ ] Return `ToolResult.ok(...)` with output matching the schema below.
- [ ] Catch `GhostfolioClientError` and map to `ToolResult.fail(error_code, ...)`.
- [ ] Never leak raw exception details to user-facing output.
- [ ] Round all monetary values to 2 decimal places.
- [ ] Add full type hints and a concise Google-style docstring.

#### B. Output Schema

```python
{
    "tax_year": int,
    "income_bracket": str,
    "short_term": {
        "total_gains": float,
        "total_losses": float,
        "net": float,
        "estimated_tax": float,
        "rate_applied": float,
    },
    "long_term": {
        "total_gains": float,
        "total_losses": float,
        "net": float,
        "estimated_tax": float,
        "rate_applied": float,
    },
    "combined_liability": float,
    "per_asset": [
        {
            "symbol": str,
            "gain_loss": float,
            "holding_period": "short_term" | "long_term",
            "cost_basis": float,
            "proceeds": float,
        }
    ],
    "disclaimer": "Simplified estimate using FIFO. Not financial advice.",
}
```

#### C. Unit Tests (`agent/tests/unit/test_tax_estimator.py`)

- [ ] **Happy path with hand-verified values:** Create a fixture with known BUY/SELL pairs where expected gains/losses can be computed by hand. Assert exact dollar amounts match.
- [ ] **Short-term vs long-term classification:** One sale within 365 days of purchase (short-term) and one sale after 365 days (long-term). Assert correct classification and different tax rates.
- [ ] **No realized gains (buys only):** Only BUY transactions, no SELLs. Assert `success=True` with zero liability.
- [ ] **Invalid tax year:** Year out of range returns `INVALID_TAX_YEAR`.
- [ ] **Invalid income bracket:** Bad bracket returns `INVALID_INCOME_BRACKET`.
- [ ] **Client error mapping:** `GhostfolioClientError` mapped to `ToolResult.fail(error_code)`.
- [ ] **Recommended extra:** Multiple lots consumed by a single SELL (partial lot consumption).

#### D. Test Fixture (`agent/tests/fixtures/orders_tax_scenarios.json`)

Create a deterministic fixture with hand-calculable tax scenarios:

- **AAPL:** BUY 10 shares @ $100 on 2024-01-15, SELL 5 shares @ $150 on 2024-06-15 (short-term, ~152 days)
  - Expected: gain = 5 * ($150 - $100) = $250 short-term
- **MSFT:** BUY 8 shares @ $200 on 2023-01-10, SELL 4 shares @ $250 on 2024-06-10 (long-term, ~517 days)
  - Expected: gain = 4 * ($250 - $200) = $200 long-term
- **TSLA:** BUY 6 shares @ $300 on 2024-03-01, SELL 3 shares @ $250 on 2024-09-01 (short-term loss, ~184 days)
  - Expected: loss = 3 * ($250 - $300) = -$150 short-term
- Include some DIVIDEND/FEE activities to confirm they are correctly ignored.

Hand-verified expected totals (middle bracket):
- Short-term net: $250 + (-$150) = $100, tax @ 24% = $24.00
- Long-term net: $200, tax @ 15% = $30.00
- Combined liability: $54.00

---

## Important Context

### Files to Modify

| File                                          | Action                                                         |
| --------------------------------------------- | -------------------------------------------------------------- |
| `agent/tools/tax_estimator.py`                | Replace placeholder with FIFO tax estimation tool              |
| `agent/tests/unit/test_tax_estimator.py`      | Create unit tests with hand-verified ground truth values       |
| `agent/tests/fixtures/orders_tax_scenarios.json` | Add deterministic fixture for tax calculation test vectors  |
| `agent/tests/conftest.py`                     | Optional fixture additions only if needed                      |

### Files You Should NOT Modify

- No Ghostfolio app code (`apps/api`, `apps/client`, `libs/*`) for this ticket.
- No Docker/compose changes needed for this ticket.
- No auth/client refactors unless a blocker is discovered.
- Do not modify existing fixtures (`orders.json`, `orders_mixed_types.json`).

### Cursor Rules to Follow

- `.cursor/rules/agent-patterns.mdc` — pure tools with injected `api_client`
- `.cursor/rules/error-handling.mdc` — errors as values, taxonomy-aligned codes
- `.cursor/rules/tdd-methodology.mdc` — minimum 3 tests per unit; financial calculations MUST have hand-verified ground truth
- `.cursor/rules/ghostfolio-integration.mdc` — endpoint + type conventions
- `.cursor/rules/python-code-style.mdc` — hints/docstrings/import order

### API Contract Used by This Tool

| Method                              | Endpoint                    | Notes                         |
| ----------------------------------- | --------------------------- | ----------------------------- |
| `api_client.get_orders()`           | `GET /api/v1/order`         | Bearer auth handled by client |

Activity fields used by FIFO algorithm:
- `type`: filter for `"BUY"` and `"SELL"` only
- `date`: ISO 8601 string, used for holding period calculation
- `quantity`: number of shares/units
- `unitPrice`: price per share at transaction time
- `SymbolProfile.symbol`: grouping key for per-asset lot tracking

---

## Key Complexity Notes

1. **Partial lot consumption:** A single SELL may consume parts of multiple BUY lots. A single BUY lot may be partially consumed across multiple SELLs. Track remaining quantity per lot.
2. **Date parsing:** Activity dates are ISO 8601 strings (`"2024-01-15T00:00:00.000Z"`). Parse with `datetime.fromisoformat()` or similar.
3. **Year filtering:** Fetch all orders (no range filter), then filter SELLs to `tax_year`. BUYs from any prior year are eligible as cost basis lots.
4. **Tax on net gains only:** If net is negative (loss), `estimated_tax` should be `0.0` for that category. Losses are reported but not taxed.
5. **Rounding:** All monetary values rounded to 2 decimal places in the final output.

---

## Definition of Done for TICKET-05

- [ ] `agent/tools/tax_estimator.py` implemented as pure async function using injected client.
- [ ] Input validation for `tax_year` and `income_bracket`; invalid values return structured errors.
- [ ] FIFO lot matching algorithm correctly consumes oldest BUY lots first.
- [ ] Short-term vs long-term classification based on 365-day threshold.
- [ ] Tax rates applied per income bracket.
- [ ] All monetary values rounded to 2 decimal places.
- [ ] Unit tests with hand-verified ground truth values passing.
- [ ] Full unit suite still passing: `pytest agent/tests/unit/`
- [ ] `docs/tickets/devlog.md` updated after completion.
- [ ] Work committed on ticket branch (`feature/TICKET-05-tax-estimator`) with `--no-verify`.

---

## Estimated Time: 75-120 minutes

| Task                                            | Estimate  |
| ----------------------------------------------- | --------- |
| Design FIFO algorithm + fixture with hand math  | 20 min    |
| Implement tool function + FIFO logic            | 30 min    |
| Add unit tests with ground truth assertions     | 25 min    |
| Run unit tests + fix failures                   | 15 min    |
| Devlog + branch commit workflow                 | 10 min    |

---

## After TICKET-05: What Comes Next

- **TICKET-06: Asset Allocation Advisor** — analyze current vs target allocation using pre-computed Ghostfolio holding data, flag concentration risks.
