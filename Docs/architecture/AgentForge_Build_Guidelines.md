# AgentForge — Build Guidelines

**Ghostfolio + AI Agent Integration**
Prepared by: Alex | February 23, 2026 | Version 1.1

> Incorporates corrections from Ghostfolio README review: Bearer token auth flow, corrected Docker Compose paths, expanded activity types, mandatory API discovery phase, and undocumented API risk mitigations.

---

## 1. Architecture Decision Records (ADRs)

### ADR-001: Orchestration Framework — LangGraph

| Field | Detail |
|-------|--------|
| **Status** | Accepted |
| **Context** | We need an orchestration framework for a single financial AI agent with 4 deterministic tools, strict validation gates, and an audit-friendly execution model. The 2-week sprint demands reliability over rapid prototyping. |
| **Options Considered** | (A) LangGraph — graph-based, explicit state transitions. (B) CrewAI — role-based multi-agent. (C) Hybrid LangGraph + CrewAI role abstractions. |
| **Decision** | **LangGraph.** |
| **Rationale** | Financial workflows require deterministic control over execution flow. LangGraph's explicit state machine model lets us enforce validation gates between steps, implement proper error recovery, and maintain a clear audit trail. CrewAI's multi-agent abstraction adds unnecessary token cost and unpredictability for what is fundamentally a single agent with multiple tools. The hybrid approach over-engineers a 2-week project. |
| **Tradeoffs** | Steeper learning curve, more boilerplate than CrewAI, debugging complex graphs requires LangSmith. |
| **Risks** | Graph complexity may grow unwieldy if scope creeps beyond 6 nodes. |
| **Mitigations** | Lock the topology at 6 nodes (Router → Tool Executor → Validator → Synthesizer → Clarifier → Error Handler). No new nodes without ADR amendment. |

---

### ADR-002: LLM Provider — OpenAI GPT-4o

| Field | Detail |
|-------|--------|
| **Status** | Accepted |
| **Context** | The agent needs reliable function calling, fast inference for a live demo, and strong numerical reasoning for financial calculations. |
| **Options Considered** | (A) GPT-4o. (B) Claude 3.5 Sonnet. (C) Open-source via Groq (Llama 3.1 70B). |
| **Decision** | **GPT-4o.** |
| **Rationale** | Best-in-class function calling with structured JSON output mode. Fastest inference among frontier models for a snappy demo. Widest LangChain/LangGraph ecosystem support. Claude is a strong alternative but GPT-4o's speed wins for live presentation. Open-source models are a false economy — hours lost to tool-call reliability exceed any cost savings. |
| **Tradeoffs** | Higher token cost, vendor lock-in, occasional hallucination on precise financial figures. |
| **Risks** | Rate limits on free tier can break the demo. |
| **Mitigations** | Upgrade to paid tier ($5 minimum credit). Implement 60-second TTL cache on Ghostfolio API responses. Pre-warm LLM connection on FastAPI startup. |

---

### ADR-003: Conversational Memory — LangGraph Built-in Checkpointer

| Field | Detail |
|-------|--------|
| **Status** | Accepted |
| **Context** | The agent needs conversation persistence, thread isolation, and the ability to reference earlier context within a session. |
| **Options Considered** | (A) LangGraph MemorySaver / SqliteSaver. (B) Custom memory with ChromaDB vector store. (C) Redis-backed session memory with TTL. |
| **Decision** | **LangGraph MemorySaver (dev) / SqliteSaver (demo).** |
| **Rationale** | Zero additional infrastructure. Automatic state serialization at every graph node. Thread-based conversation isolation out of the box. Supports replay/fork from any checkpoint. Directly satisfies the grading rubric's memory requirement. A vector store is a time trap for a 2-week sprint. |
| **Tradeoffs** | No semantic search over past conversations. Full state serialization can be memory-heavy with long conversations. |
| **Risks** | SQLite doesn't scale horizontally (irrelevant for this project). |
| **Mitigations** | Use MemorySaver for development speed, switch to SqliteSaver for the demo to demonstrate persistence across restarts. |

---

### ADR-004: Backend Architecture — Python FastAPI Sidecar

| Field | Detail |
|-------|--------|
| **Status** | Accepted |
| **Context** | The agent backend must run LangGraph, expose an SSE streaming endpoint, and communicate with Ghostfolio's API. Ghostfolio's own backend is NestJS (TypeScript). |
| **Options Considered** | (A) Python FastAPI sidecar service. (B) Embedded NestJS module within Ghostfolio. (C) Serverless functions (AWS Lambda). |
| **Decision** | **Python FastAPI sidecar.** |
| **Rationale** | LangGraph's Python implementation is 6+ months ahead of the JS version. FastAPI's async support handles SSE streaming naturally. Complete separation from Ghostfolio's codebase means a clean fork diff. Docker Compose bundles everything into a single `docker compose up`. This is how Stripe, Notion, and Linear run their AI features — as separate services. |
| **Tradeoffs** | Two backend services to run (Docker Compose manages this). CORS configuration required. Extra network hop between agent and Ghostfolio API. |
| **Risks** | Cross-origin issues between Angular frontend and FastAPI. |
| **Mitigations** | Configure CORS in FastAPI on day 1. Use Docker networking so services communicate via internal hostnames. |

---

### ADR-005: Frontend Integration — Floating Chat Widget

| Field | Detail |
|-------|--------|
| **Status** | Accepted |
| **Context** | The agent needs a user-facing interface within Ghostfolio's existing Angular application. We must minimize modifications to Ghostfolio's codebase. |
| **Options Considered** | (A) Floating FAB + slide-out chat panel. (B) Dedicated `/agent` page. (C) Inline "Ask AI" buttons on existing pages. |
| **Decision** | **Floating chat widget (FAB + slide-out panel).** |
| **Rationale** | Zero modification to existing Ghostfolio components. Accessible from every page. Familiar UX pattern (Intercom/Drift). Built as a single lazy-loaded Angular feature module in the Nx workspace. Only existing file touched: app routing module (one line to lazy-load the agent module). |
| **Tradeoffs** | Feels "bolted on" vs deeply integrated. Limited screen real estate for rich data. |
| **Risks** | Mobile responsiveness requires extra work. |
| **Mitigations** | Use Angular CDK overlay system. Use Angular Material components consistent with Ghostfolio's existing UI. Responsive breakpoints for mobile. |

---

### ADR-006: Response Streaming — SSE with Typed Events

| Field | Detail |
|-------|--------|
| **Status** | Accepted |
| **Context** | The agent needs to stream responses to the frontend for responsive UX during multi-step tool execution. |
| **Options Considered** | (A) SSE with typed events. (B) WebSocket. (C) Polling. |
| **Decision** | **SSE with typed event protocol.** |
| **Event Types** | `thinking` (agent is processing), `tool_call` (executing tool with name/args), `tool_result` (tool returned data), `token` (incremental text), `done` (final response). |
| **Rationale** | Native browser support, unidirectional streaming is sufficient for chat, works through all proxies. FastAPI's `StreamingResponse` + async generators + LangGraph's `astream_events()` make implementation clean. Use `fetch` + `getReader()` on Angular side (not `EventSource`, since we need POST support). |
| **Tradeoffs** | Unidirectional — client can't send mid-stream cancellation easily. Reconnection logic needed. |
| **Risks** | Dropped connections during long tool chains. |
| **Mitigations** | Implement auto-reconnect with exponential backoff. Keep tool chains under 30 seconds total. |

---

### ADR-007: Error Handling — Defensive Tool Design with Validation Gates

| Field | Detail |
|-------|--------|
| **Status** | Accepted |
| **Context** | Financial calculations demand correctness. The LLM can hallucinate ticker symbols, malform arguments, or produce nonsensical numbers. |
| **Options Considered** | (A) Validation gates + structured error objects. (B) LLM self-correction with reflection loop. (C) Guardrails AI framework. |
| **Decision** | **Defensive tool design with validation gates.** |
| **Rationale** | Never trust the LLM to be correct about numbers. Every tool validates inputs against a schema, returns structured error objects (`{success: false, error: 'INVALID_TICKER', ...}`), and the graph includes an explicit error-handling node for retry/fallback/explanation. This is deterministic, testable, and debuggable. Reflection loops double token cost and are unreliable. Guardrails adds a framework dependency without clear benefit. |
| **Tradeoffs** | More code per tool (schema validation + error types). Upfront error taxonomy design. |
| **Risks** | Over-validation makes the agent feel rigid. |
| **Mitigations** | Validate critical fields (tickers, dates, numerical ranges) but allow flexible free-text inputs. |

---

### ADR-008: Fork Strategy — Surgical Additions Only

| Field | Detail |
|-------|--------|
| **Status** | Accepted |
| **Context** | We're building on a forked Ghostfolio repo. We need to minimize merge conflicts and make our contributions clearly distinguishable from upstream code. |
| **Options Considered** | (A) New files only, zero modifications to existing files. (B) Strategic modifications to 5-10 existing files. (C) Full fork divergence. |
| **Decision** | **Surgical additions — all agent code in new files.** |
| **Rationale** | Git diff is clean: almost entirely new file additions. Zero risk of breaking existing Ghostfolio functionality. Graders can see exactly what we added. Can rebase on upstream updates without conflicts. |
| **Implementation** | Angular agent feature using **standalone components** (Ghostfolio uses `bootstrapApplication()` with standalone components, not NgModules). Files: `agent-page.routes.ts`, standalone components for FAB, chat panel, blocks, and `agent.service.ts`. Only 3 existing files modified: (1) `app.routes.ts` — one lazy-load route, (2) `app.component.ts` — add FAB component to standalone `imports` array, (3) `app.component.html` — one line for the FAB overlay. |
| **Tradeoffs** | Can't leverage Ghostfolio's existing Angular components directly. Some code duplication. |
| **Risks** | Agent module must be entirely self-contained. |
| **Mitigations** | Import Angular Material directly in agent module. Use Ghostfolio's design tokens (CSS variables) for visual consistency. |

---

### ADR-009: Authentication Strategy — Ghostfolio Bearer Token Flow

| Field | Detail |
|-------|--------|
| **Status** | Accepted |
| **Context** | The agent service must authenticate with Ghostfolio's API to fetch portfolio data, import activities, and access account endpoints. Ghostfolio's README reveals an auth flow different from standard JWT passthrough. |
| **Discovery** | Ghostfolio uses a **security-token → Bearer token** flow. The client sends `POST /api/v1/auth/anonymous` with `{"accessToken": "<SECURITY_TOKEN>"}` and receives a Bearer token in response. This Bearer token is then used in the `Authorization` header for all subsequent API calls. |
| **Options Considered** | (A) Browser JWT passthrough (original assumption — **INCORRECT**). (B) Agent-managed Bearer token lifecycle via `/api/v1/auth/anonymous`. (C) Direct database access bypassing auth. |
| **Decision** | **Agent-managed Bearer token lifecycle (Option B).** |
| **Implementation** | Create `auth.py` module: on startup, POST to `/api/v1/auth/anonymous` with the security token from env vars, store the Bearer token in memory, implement auto-refresh on 401 responses, expose a `get_auth_header()` helper for all API calls. |
| **Tradeoffs** | Must manage token lifecycle (expiry, refresh). Depends on Ghostfolio's undocumented token TTL. |
| **Risks** | Token expiry mid-demo. Ghostfolio's internal API may reject the Bearer token for certain endpoints. |
| **Mitigations** | Pre-warm auth on FastAPI startup (fail fast). Implement proactive token refresh every 15 minutes. Add a health check that verifies auth status before demo. Log all 401/403 responses for debugging. |

---

## 2. Component Architecture

### System Topology

```
┌─────────────────────────────────────────────────────┐
│                    User's Browser                    │
│  ┌───────────────────────────────────────────────┐  │
│  │         Ghostfolio Angular App (Nx)            │  │
│  │  ┌─────────────┐  ┌────────────────────────┐  │  │
│  │  │ Existing UI │  │ Agent Module (lazy)     │  │  │
│  │  │ (untouched) │  │  ├─ FAB Component       │  │  │
│  │  │             │  │  ├─ Chat Panel          │  │  │
│  │  │             │  │  ├─ Message Renderer    │  │  │
│  │  │             │  │  │   ├─ TextBlock       │  │  │
│  │  │             │  │  │   ├─ TableBlock      │  │  │
│  │  │             │  │  │   ├─ MetricCard      │  │  │
│  │  │             │  │  │   └─ ChartBlock      │  │  │
│  │  │             │  │  └─ Agent Service (HTTP)│  │  │
│  │  └─────────────┘  └────────────────────────┘  │  │
│  └───────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │ SSE (POST /api/chat)
                       ▼
┌──────────────────────────────────────────────────────┐
│              FastAPI Agent Service (:8000)            │
│  ┌──────────┐  ┌──────────────────────────────────┐  │
│  │ auth.py  │  │ LangGraph (6-node topology)      │  │
│  │ Bearer   │  │  Router → Tool Executor →        │  │
│  │ token    │  │  Validator → Synthesizer          │  │
│  │ manager  │  │  Clarifier ↗  Error Handler ↗    │  │
│  └──────┬───┘  └───────────────┬──────────────────┘  │
│         │                      │                      │
│         │      ┌───────────────┼──────────────┐      │
│         │      │  4 Tools (pure functions)     │      │
│         │      │  ├─ Portfolio Analyzer        │      │
│         │      │  ├─ Transaction Categorizer   │      │
│         │      │  ├─ Capital Gains Estimator   │      │
│         │      │  └─ Asset Allocation Advisor  │      │
│         │      └───────────────┬──────────────┘      │
│         │                      │                      │
│  ┌──────┴──────────────────────┴──────────────────┐  │
│  │         GhostfolioClient (httpx)               │  │
│  │  • Auth: Bearer token via /api/v1/auth/anonymous│  │
│  │  • 60s TTL cache (cachetools)                  │  │
│  │  • Auto-refresh on 401                         │  │
│  └────────────────────┬───────────────────────────┘  │
└───────────────────────┼──────────────────────────────┘
                        │ HTTP (internal Docker network)
                        ▼
┌──────────────────────────────────────────────────────┐
│           Ghostfolio NestJS Backend (:3333)           │
│  ┌──────────┐  ┌───────────┐  ┌───────────────────┐ │
│  │ Auth API │  │ Portfolio │  │ Import/Activities │ │
│  │ /api/v1/ │  │ Endpoints │  │ POST /api/v1/     │ │
│  │ auth/    │  │ (internal,│  │ import            │ │
│  │ anonymous│  │ undoc'd)  │  │ (documented)      │ │
│  └──────────┘  └─────┬─────┘  └───────────────────┘ │
└───────────────────────┼──────────────────────────────┘
                        │
           ┌────────────┼────────────┐
           ▼                         ▼
    ┌─────────────┐          ┌─────────────┐
    │ PostgreSQL  │          │    Redis     │
    │  (:5432)    │          │   (:6379)    │
    └─────────────┘          └─────────────┘
```

### State Ownership Map

| State | Owner | Persistence | Notes |
|-------|-------|-------------|-------|
| Conversation messages | LangGraph checkpointer | SqliteSaver (per-thread) | Survives restarts |
| Portfolio snapshot | LangGraph `AgentState` | Per-turn (in-memory) | Cached 60s via TTL |
| Bearer token | `auth.py` module | In-memory (refreshable) | Auto-refresh on 401 or every 15 min |
| Tool call history | LangGraph `AgentState` | Per-turn | Powers SSE `tool_call` events |
| User preferences | LangGraph `AgentState` | Per-thread via checkpointer | Risk tolerance, display prefs |
| Chat UI state | Angular `AgentService` | Component lifetime | Messages, loading states |
| Ghostfolio API cache | `cachetools.TTLCache` | In-memory, 60s TTL | Prevents redundant API calls |

---

## 3. LangGraph Topology

### 6-Node Graph Definition

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
              ┌─────│   Router    │─────┐
              │     └──────┬──────┘     │
              │            │            │
         (ambiguous)  (tool needed)  (no tool)
              │            │            │
              ▼            ▼            ▼
       ┌───────────┐ ┌──────────┐ ┌───────────┐
       │ Clarifier │ │  Tool    │ │Synthesizer│
       └─────┬─────┘ │ Executor │ └─────┬─────┘
             │        └────┬─────┘       │
             │             │             │
             │             ▼             │
             │      ┌─────────────┐      │
             │      │  Validator  │      │
             │      └──┬───────┬──┘      │
             │   (pass)│       │(fail)   │
             │         ▼       ▼         │
             │  ┌───────────┐ ┌────────┐ │
             │  │Synthesizer│ │ Error  │ │
             │  └─────┬─────┘ │Handler │ │
             │        │       └───┬────┘ │
             │        │           │      │
             └────────┴───────────┴──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │     END     │
                    └─────────────┘
```

### Node Responsibilities

| Node | Input | Output | Logic |
|------|-------|--------|-------|
| **Router** | User message + conversation history | Tool selection or routing decision | LLM classifies intent → selects tool, clarify, or direct synthesis |
| **Tool Executor** | Tool name + validated arguments | Raw tool result (ToolResult) | Calls the selected tool with injected GhostfolioClient |
| **Validator** | ToolResult from executor | Pass/fail decision | Checks: success flag, data non-null, numerical sanity (returns between -100% and +10,000%), ticker validity |
| **Synthesizer** | Validated tool results + conversation context | Structured response blocks (text, table, chart, metric) | LLM formats results into user-facing response with typed blocks |
| **Clarifier** | Ambiguous user message | Clarification question + capability list | Acknowledges query, explains capabilities, suggests closest relevant action |
| **Error Handler** | Failed ToolResult or validation failure | Graceful error message + recovery suggestion | Explains what went wrong, suggests what the user can try instead |

### AgentState Schema

```python
from typing import TypedDict, Optional, Annotated
from langgraph.graph import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]       # Conversation history
    portfolio_snapshot: Optional[dict]             # Cached portfolio data (60s TTL)
    tool_call_history: list[dict]                  # Tool calls this turn (for SSE UI)
    pending_action: Optional[dict]                 # Reserved for human-in-the-loop
    error: Optional[str]                           # Last error for recovery routing
```

---

## 4. Tool Contracts

All tools follow the **pure function with dependency injection** pattern. No tool calls the LLM directly. No tool raises exceptions — errors are values.

### ToolResult Contract

```python
@dataclass
class ToolResult:
    success: bool
    data: dict | None
    error: str | None
    metadata: dict          # API response time, data freshness, cache hit
```

---

### Tool 1: Portfolio Performance Analyzer

```
Name:        analyze_portfolio_performance
Description: Retrieves and analyzes the user's portfolio returns, allocation
             drift, and benchmark comparison.
USE WHEN:    User asks about performance, returns, how their portfolio is doing,
             gains/losses, portfolio overview, or "how am I doing?"
DO NOT USE:  When user asks about individual transactions, tax implications,
             or wants to categorize expenses.

Input Schema:
  time_period: str    # Must be one of Ghostfolio's supported DateRange values:
                      # "1d", "wtd", "mtd", "ytd", "1y", "5y", "max"
                      # (all lowercase — Ghostfolio also supports year strings like "2024", "2025")

Output Schema (ToolResult.data):
  {
    "total_return_pct": float,
    "total_return_abs": float,
    "currency": str,
    "holdings_count": int,
    "top_performers": [{"symbol": str, "return_pct": float}],
    "bottom_performers": [{"symbol": str, "return_pct": float}],
    "allocation": {"stocks": float, "bonds": float, "cash": float, ...},
    "period": str
  }

API Note:
  - Performance endpoint is GET /api/v2/portfolio/performance (versioned as v2)
  - Response type: PortfolioPerformanceResponse { chart, firstOrderDate, performance }
  - performance contains: netPerformance, netPerformancePercentage, totalInvestment,
    currentValueInBaseCurrency, annualizedPerformancePercent

Validation:
  - time_period must be one of: "1d", "wtd", "mtd", "ytd", "1y", "5y", "max"
  - Returns between -100% and +10,000%
  - holdings_count >= 0
```

---

### Tool 2: Transaction Categorizer

```
Name:        categorize_transactions
Description: Fetches and categorizes the user's recent transactions with smart
             labeling by type, frequency, and asset class.
USE WHEN:    User asks about their transactions, activity history, what they've
             bought/sold, dividends received, fees paid, or "show my activity."
DO NOT USE:  When user asks about overall portfolio performance, tax estimates,
             or allocation advice.

Input Schema:
  days_back: int = 90    # How far back to look (default 90 days)
  type_filter: str|None  # Optional: "BUY", "SELL", "DIVIDEND", "FEE",
                         #           "INTEREST", "LIABILITY"

Output Schema (ToolResult.data):
  {
    "total_transactions": int,
    "by_type": {
      "BUY": [{"symbol": str, "date": str, "quantity": float,
               "unitPrice": float, "currency": str, "dataSource": str}],
      "SELL": [...],
      "DIVIDEND": [...],
      "FEE": [...],
      "INTEREST": [...],
      "LIABILITY": [...]
    },
    "summary": {
      "total_invested": float,
      "total_dividends": float,
      "total_fees": float,
      "most_traded_symbol": str
    }
  }

Validation:
  - days_back between 1 and 3650
  - type_filter must be one of 6 valid types if provided
  - All activity types supported: BUY, SELL, DIVIDEND, FEE, INTEREST, LIABILITY
  - Each activity includes required fields: currency, date, fee, quantity, symbol, type, unitPrice
  - Note: `dataSource` is optional for FEE, INTEREST, and LIABILITY types (backend resolves default)
  - API endpoint: GET /api/v1/order (returns { activities: Activity[], count: number })
```

---

### Tool 3: Capital Gains Tax Estimator

```
Name:        estimate_capital_gains_tax
Description: Calculates estimated capital gains tax liability using FIFO
             cost-basis tracking with short-term vs long-term classification.
USE WHEN:    User asks about taxes, tax implications, capital gains, tax-loss
             harvesting, "what do I owe?", or cost basis.
DO NOT USE:  When user asks about current performance, transaction history
             without tax context, or allocation.

Input Schema:
  tax_year: int = 2025   # Year to estimate
  income_bracket: str = "middle"  # "low", "middle", "high" for bracket estimation

Output Schema (ToolResult.data):
  {
    "tax_year": int,
    "short_term": {
      "total_gains": float,
      "total_losses": float,
      "net": float,
      "estimated_tax": float,
      "rate_applied": float
    },
    "long_term": {
      "total_gains": float,
      "total_losses": float,
      "net": float,
      "estimated_tax": float,
      "rate_applied": float
    },
    "combined_liability": float,
    "per_asset": [
      {"symbol": str, "gain_loss": float, "holding_period": str,
       "cost_basis": float, "proceeds": float}
    ],
    "disclaimer": "Simplified estimate using FIFO. Not financial advice."
  }

Algorithm:
  1. Group transactions by symbol (filter for BUY and SELL types only)
  2. Sort purchases by date ascending (FIFO order)
  3. For each SELL, consume oldest BUY lots first
  4. Cost basis = unitPrice × quantity (per lot)
  5. Holding period > 365 days → long-term; otherwise short-term
  6. Long-term rates: 0% / 15% / 20% based on income_bracket
  7. Short-term rates: 22% / 24% based on income_bracket

Validation:
  - tax_year between 2020 and current year
  - income_bracket must be one of 3 valid values
  - All monetary values rounded to 2 decimal places
```

---

### Tool 4: Asset Allocation Advisor

```
Name:        advise_asset_allocation
Description: Analyzes current asset allocation against standard targets
             and identifies concentration risks or rebalancing opportunities.
USE WHEN:    User asks about diversification, allocation, "am I balanced?",
             rebalancing, concentration risk, or "should I adjust?"
DO NOT USE:  When user asks about specific transaction history, tax estimates,
             or raw performance numbers.

Input Schema:
  target_profile: str = "balanced"  # "conservative", "balanced", "aggressive"

API Note:
  - Use GET /api/v1/portfolio/details?range=max for full holdings with allocation data
  - Ghostfolio pre-computes `allocationInPercentage` per holding — use this directly
  - Each holding includes `assetClass` (enum: EQUITY, FIXED_INCOME, LIQUIDITY, COMMODITY,
    REAL_ESTATE, ALTERNATIVE_INVESTMENT) and `assetSubClass` (enum: STOCK, ETF, BOND,
    CRYPTOCURRENCY, CASH, MUTUALFUND, PRECIOUS_METAL, PRIVATE_EQUITY, COLLECTIBLE, COMMODITY)
  - Holdings also include `sectors`, `countries`, and `markets` for deeper analysis

Output Schema (ToolResult.data):
  {
    "current_allocation": {
      "EQUITY": float, "FIXED_INCOME": float, "LIQUIDITY": float,
      "COMMODITY": float, "REAL_ESTATE": float, "ALTERNATIVE_INVESTMENT": float
    },
    "target_allocation": {
      "EQUITY": float, "FIXED_INCOME": float, "LIQUIDITY": float,
      "COMMODITY": float, "REAL_ESTATE": float, "ALTERNATIVE_INVESTMENT": float
    },
    "drift": {
      "EQUITY": float, "FIXED_INCOME": float, ...   # positive = overweight
    },
    "concentration_warnings": [
      {"symbol": str, "pct_of_portfolio": float, "threshold": float}
    ],
    "rebalancing_suggestions": [str],
    "disclaimer": "Analysis for informational purposes only. Not financial advice."
  }

Validation:
  - target_profile must be one of 3 valid values
  - All allocations sum to ~100% (±1% for rounding)
  - Concentration threshold: warn if any single asset > 25% of portfolio
```

---

## 5. Execution Discipline

### Coding Standards

| Rule | Detail |
|------|--------|
| **Type hints** | All function signatures must have full type annotations |
| **Docstrings** | Google-style docstrings on all public functions |
| **Tool pattern** | Pure functions, dependency injection, `ToolResult` returns, no exceptions |
| **Error handling** | Errors as values, never bare `except:`, always log before returning error |
| **Imports** | Standard lib → third-party → local, one blank line between groups |
| **Line length** | 100 characters max |
| **Tests** | Every tool: 3 tests minimum (happy path, invalid input, API error) |

### Source Control Methodology

| Practice | Detail |
|----------|--------|
| **Branching** | `main` (protected) → feature branches (`feat/tool-portfolio`, `feat/ui-chat`, etc.) |
| **Commits** | Conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:` |
| **PRs** | All merges via PR with at least 1 review. Squash merge to main. |
| **Contract-first** | API contract (request/response schemas, SSE event format) defined Day 1 before parallel work begins |
| **Integration** | Feature branches integrate against main by Day 10. Final integration testing Days 11–12. |

### Cursor / AI-Assisted Development Strategy

| Approach | Detail |
|----------|--------|
| **System prompt** | Load project context: ADRs, tool contracts, ToolResult schema, LangGraph topology |
| **Guardrails** | Never let Cursor auto-generate financial calculations without manual review |
| **Best use** | Boilerplate generation (FastAPI routes, Angular component scaffolding, test fixtures) |
| **Avoid** | Auto-generating tool descriptions (must be hand-crafted for routing accuracy) |
| **Review** | Every AI-generated code block reviewed against the ToolResult contract before merge |

---

## 6. TDD Strategy

### Three Testing Layers

**Layer 1: Unit Tests (per tool, mocked API)**
- 3 tests per tool minimum: happy path, invalid input, API error
- Use `pytest` with `httpx` mock / `respx` for API mocking
- Run in milliseconds, zero network calls
- Execute on every commit via pre-commit hook

**Layer 2: Integration Tests (graph routing, mocked tools)**
- Mock all 4 tools with deterministic returns
- Send 5 canonical queries, assert correct tool routing and state transitions
- Verify: Router → correct tool → Validator passes → Synthesizer produces blocks
- Verify: ambiguous query → Clarifier node activated
- Verify: tool failure → Error Handler produces graceful message

**Layer 3: Golden-Path E2E (real LLM, test data)**
- 5 scripted scenarios in a Jupyter notebook
- Run with real GPT-4o calls against Ghostfolio with seeded data
- Eyeball results, snapshot outputs for regression detection
- Run manually before demo: 30 minutes per pass
- Doubles as demo rehearsal

### Test File Structure

```
/agent
  /tests
    /unit
      test_portfolio_analyzer.py
      test_transaction_categorizer.py
      test_tax_estimator.py
      test_allocation_advisor.py
      test_auth.py
    /integration
      test_graph_routing.py
      test_state_transitions.py
    /e2e
      golden_path.ipynb
    conftest.py           # Shared fixtures, mock client factory
```

---

## 7. Sprint Plan (2-Week)

### Week 1: Foundation & Core Agent

| Day | Owner | Deliverables | Type |
|-----|-------|-------------|------|
| **1** | All | Define API contract (OpenAPI spec for `/api/chat`). Define SSE event schema. Set up monorepo structure. Configure Docker Compose with `docker/docker-compose.yml`. Create `.env.example` with all Ghostfolio vars. | `[SETUP]` `[DOCS]` |
| **2** | Agent dev | **CRITICAL — API Discovery Phase.** Run Ghostfolio in Docker. Open browser DevTools → Network tab. Navigate through all Ghostfolio pages. Document every internal API endpoint (method, path, request/response shape). Map endpoints to our 4 tools. Save as `ghostfolio-api-map.md`. | `[SETUP]` `[DOCS]` |
| **3** | Agent dev | Implement `auth.py` — Bearer token lifecycle via `POST /api/v1/auth/anonymous`. Implement `GhostfolioClient` with auth header injection, 60s TTL cache, auto-refresh on 401. Write `test_auth.py`. | `[CODE]` `[TEST]` |
| **3** | Frontend dev | Scaffold Angular agent module (FAB component, chat panel, agent service). Connect to mock SSE endpoint. | `[CODE]` |
| **4** | Agent dev | Build LangGraph 6-node topology (Router, Tool Executor, Validator, Synthesizer, Clarifier, Error Handler). Wire up conditional edges. Verify with integration test. | `[CODE]` `[TEST]` |
| **4** | Frontend dev | Build message renderer components (TextBlock, TableBlock, MetricCard, ChartBlock). Consume typed SSE events. | `[CODE]` |
| **5** | Agent dev | Implement Tool 1 (Portfolio Analyzer) + unit tests. Implement Tool 2 (Transaction Categorizer) + unit tests. | `[CODE]` `[TEST]` |
| **5** | Frontend dev | Polish chat UI. Add loading states, step-by-step progress indicators from `tool_call` SSE events. | `[CODE]` |

### Week 2: Remaining Tools, Integration & Polish

| Day | Owner | Deliverables | Type |
|-----|-------|-------------|------|
| **6** | Agent dev | Implement Tool 3 (Tax Estimator, FIFO algorithm) + unit tests. Implement Tool 4 (Allocation Advisor) + unit tests. | `[CODE]` `[TEST]` |
| **6** | Frontend dev | Integrate real SSE endpoint (replace mocks). CORS configuration. | `[CODE]` |
| **7** | All | System prompt engineering. Write tool descriptions with positive/negative examples. Test routing accuracy across 10+ queries. Iterate descriptions until routing is >90% accurate. | `[CODE]` `[TEST]` |
| **8** | All | Full integration testing. Docker Compose end-to-end. Seed database with demo portfolio data. Fix integration bugs. | `[TEST]` |
| **9** | All | Edge case hardening (empty portfolio, single asset, nonsense query, prompt injection, ambiguous ticker, future dates). Write adversarial grader test kit. | `[TEST]` |
| **10** | All | README (architecture diagram, LangGraph visualization, quick-start, tool table, demo GIF). ADR-009 writeup. `ghostfolio-api-map.md` cleanup. | `[DOCS]` |
| **11** | All | Demo rehearsal #1 — full run-through with narration. Record backup video. Fix any issues. | `[REVIEW]` |
| **12** | All | Demo rehearsal #2. Smoke test morning-of. Buffer day for any remaining fixes. | `[REVIEW]` |

### Scope Cut Triggers

If behind schedule at the end of Week 1, cut immediately to MVP:

| Keep (MVP) | Cut |
|------------|-----|
| Portfolio Analyzer (Tool 1) | Chart rendering (use text tables) |
| Transaction Categorizer (Tool 2) | Tax Estimator (Tool 3) |
| Basic chat UI (text only) | Allocation Advisor (Tool 4) |
| Docker Compose (4 services) | Advanced edge case handling |
| LangGraph 3-node minimum (Router → Executor → Synthesizer) | Validator and Clarifier nodes |

A working 2-tool agent beats a broken 4-tool agent every time.

---

## 8. Risk Registry

| # | Risk | Severity | Likelihood | Impact | Mitigation |
|---|------|----------|------------|--------|------------|
| R1 | **Undocumented Ghostfolio API** — Only 3 endpoints documented in README (health, import, public portfolio). All portfolio/holdings/performance endpoints are internal and undocumented. | Critical | High | Blocks all tool development | Day 2 mandatory API Discovery phase. Browser DevTools + NestJS source code inspection. Document in `ghostfolio-api-map.md`. |
| R2 | **Tool misrouting** — LLM picks the wrong tool or fabricates arguments | Critical | Medium | Demo produces wrong results | Hand-craft tool descriptions with negative examples. Few-shot examples in system prompt. Clarifier node for low-confidence routing. |
| R3 | **Bearer token auth failure** — Token expires mid-demo or Ghostfolio rejects it | High | Medium | All API calls fail | Auto-refresh on 401. Proactive refresh every 15 min. Pre-warm auth on startup. Health check endpoint that verifies auth. |
| R4 | **LLM API latency/rate limit** — GPT-4o slow or rate-limited during demo | High | Low | Demo feels sluggish or stalls | Paid tier ($5 min). 60s response cache. Pre-warm LLM connection. SSE streaming masks latency. |
| R5 | **Docker Compose boot failure** — Services fail to start on grader's machine | High | Medium | Cannot demo at all | Health checks with `depends_on: condition: service_healthy`. Documented `.env.example`. Tested on clean machine. |
| R6 | **Financial calculation errors** — Tax estimator or allocation math is wrong | Medium | Low | Graders verify math and find errors | FIFO algorithm is deterministic, unit-tested with hand-verifiable demo data. All financial outputs rounded to 2 decimal places. |
| R7 | **Ghostfolio API schema changes** — Fork becomes incompatible with latest Ghostfolio | Medium | Low | API calls return unexpected data | Pin Ghostfolio to a specific commit hash in fork. Test against that version only. |
| R8 | **Scope creep** — Team attempts all 4 tools + rich UI when behind schedule | Medium | High | Nothing works well | Sprint plan has explicit scope cut triggers at end of Week 1. MVP is 2 tools + basic UI. |

---

## 9. Docker Stack

### Service Architecture

```yaml
# docker/docker-compose.yml (Ghostfolio's existing file)
# + docker-compose.agent.yml (our overlay)

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ghostfolio-db
      POSTGRES_USER: ghostfolio
      POSTGRES_PASSWORD: <from .env>
    ports: ["5432:5432"]
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./seed.sql:/docker-entrypoint-initdb.d/seed.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ghostfolio"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    environment:
      REDIS_PASSWORD: <from .env>
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s

  ghostfolio:
    build: ..    # Ghostfolio root
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      ACCESS_TOKEN_SALT: <from .env>
      DATABASE_URL: postgresql://ghostfolio:<pw>@postgres:5432/ghostfolio-db
      JWT_SECRET_KEY: <from .env>
      REDIS_HOST: redis
      REDIS_PASSWORD: <from .env>
      REDIS_PORT: 6379
    ports: ["3333:3333"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3333/api/v1/health"]
      interval: 10s
      timeout: 5s
      retries: 10

  agent:
    build: ../agent
    depends_on:
      ghostfolio:
        condition: service_healthy
    environment:
      OPENAI_API_KEY: <from .env>
      GHOSTFOLIO_URL: http://ghostfolio:3333
      GHOSTFOLIO_ACCESS_TOKEN: <from .env>
    ports: ["8000:8000"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
```

### Launch Commands

```bash
# Option A: Use Docker Compose override for agent service
docker compose -f docker/docker-compose.yml \
               -f docker-compose.agent.yml up -d

# Option B: Convenience script
./start.sh    # wraps the above with env validation
```

### Required Environment Variables (`.env.example`)

```bash
# === Ghostfolio Core ===
ACCESS_TOKEN_SALT=CHANGE_ME_RANDOM_STRING
JWT_SECRET_KEY=CHANGE_ME_RANDOM_STRING
POSTGRES_DB=ghostfolio-db
POSTGRES_USER=ghostfolio
POSTGRES_PASSWORD=CHANGE_ME
REDIS_HOST=redis
REDIS_PASSWORD=CHANGE_ME
REDIS_PORT=6379

# === Ghostfolio Optional ===
HOST=0.0.0.0
PORT=3333
REQUEST_TIMEOUT=2000

# === Agent Service ===
OPENAI_API_KEY=sk-...
GHOSTFOLIO_URL=http://ghostfolio:3333
GHOSTFOLIO_ACCESS_TOKEN=your-security-token

# === Optional: LangSmith Observability ===
LANGSMITH_API_KEY=ls-...
LANGCHAIN_TRACING_V2=true
```

---

## 10. Seed Data Requirements

### Demo Portfolio Spec

The seed portfolio must produce interesting results across all 4 tools:

| Requirement | Detail |
|-------------|--------|
| **Holdings** | 8–12 positions across stocks, bonds, ETFs, and optionally crypto |
| **Transactions** | 50+ historical transactions spanning 2 years |
| **Activity types** | Must include all 6: BUY, SELL, DIVIDEND, FEE, INTEREST, LIABILITY |
| **Diversity** | Mix of winners and losers for interesting performance data |
| **Tax scenarios** | Both short-term and long-term holdings for tax tool demonstration |
| **Allocation drift** | Intentionally overweight in one sector (e.g., tech) to trigger allocation warnings |
| **Data format** | Ghostfolio import format: `currency`, `dataSource`, `date` (ISO-8601), `fee`, `quantity`, `symbol`, `type`, `unitPrice` (per-unit price, NOT total cost) |
| **Data sources** | Use `YAHOO` for stocks/ETFs, `COINGECKO` for crypto, `MANUAL` for custom entries |

### Sample Seed Entry

```json
{
  "activities": [
    {
      "currency": "USD",
      "dataSource": "YAHOO",
      "date": "2024-01-15T00:00:00.000Z",
      "fee": 0,
      "quantity": 10,
      "symbol": "AAPL",
      "type": "BUY",
      "unitPrice": 185.50
    },
    {
      "currency": "USD",
      "dataSource": "YAHOO",
      "date": "2025-08-20T00:00:00.000Z",
      "fee": 4.95,
      "quantity": 5,
      "symbol": "AAPL",
      "type": "SELL",
      "unitPrice": 228.75
    },
    {
      "currency": "USD",
      "dataSource": "YAHOO",
      "date": "2025-03-15T00:00:00.000Z",
      "fee": 0,
      "quantity": 0,
      "symbol": "AAPL",
      "type": "DIVIDEND",
      "unitPrice": 0.25
    }
  ]
}
```

---

## 11. Demo Script

### Pre-Demo Checklist

- [ ] Docker Compose running, all 4 services healthy
- [ ] Bearer token auth verified (agent service startup logs show "Auth OK")
- [ ] Seed data loaded (verify via Ghostfolio UI at `http://localhost:3333`)
- [ ] Admin user created via Ghostfolio "Get Started" flow
- [ ] Backup video recorded (recorded within last 24 hours)
- [ ] LLM pre-warmed (agent service sends test completion on startup)
- [ ] Demo laptop on power, WiFi stable, screen resolution set for projector

### 5-Query Scripted Demo

**Query 1: Portfolio Health Check (multi-step showcase)**
```
User types: "How is my portfolio doing?"
```
Narration: "Watch the agent classify this as a portfolio analysis request. It calls the portfolio performance tool, which hits Ghostfolio's API to fetch all 12 holdings. Now it's comparing allocation against a 60/40 target. Here comes the synthesis — notice the metric card with total return, the pie chart showing allocation, and the table of top performers. One message triggered a 4-step reasoning chain."

Expected SSE sequence: `thinking` → `tool_call: analyze_portfolio` → `tool_result` → `token` (streaming synthesis) → `done`

---

**Query 2: Transaction Categorization (tool use)**
```
User types: "Categorize my recent transactions"
```
Narration: "The agent selects the transaction categorizer tool and fetches the last 90 days of activity. Notice it groups by type — BUY, SELL, DIVIDEND, FEE — and provides a summary with total invested and dividends received."

---

**Query 3: Tax Implications (deterministic calculation)**
```
User types: "What are my tax implications this year?"
```
Narration: "This is where deterministic code matters. The tax estimator uses FIFO cost-basis tracking — not the LLM doing math. It matches each sale against the oldest purchase lots, classifies short-term versus long-term gains, and applies the appropriate tax brackets. Every number here is verifiable."

---

**Query 4: Allocation Advice (analysis)**
```
User types: "Am I properly diversified?"
```
Narration: "The allocation advisor compares current holdings against a balanced target. It identifies that we're overweight in tech stocks and suggests rebalancing opportunities — all phrased as analysis, never as financial advice. Notice the disclaimer at the bottom."

---

**Query 5: Edge Case (graceful handling)**
```
User types: "What's the weather like?"
```
Narration: "Here's how the agent handles an out-of-scope query. Instead of crashing or giving a generic error, it acknowledges the question, explains its financial analysis capabilities, and suggests the closest thing it CAN help with. This is the Clarifier node in action."

### Fallback Plan

If the live demo fails at any point:
1. Say: "Let me show you the recorded run while we investigate."
2. Switch to backup video (recorded within 24 hours, shows the full 5-query sequence).
3. Continue narrating over the video — the narration is the same either way.
4. After video: "We've identified the issue and can discuss the architecture while we resolve it."

---

## 12. Reliability Matrix

| Scenario | Expected Behavior | Fallback | Test Coverage |
|----------|-------------------|----------|---------------|
| Empty portfolio | "No holdings yet. Add investments to Ghostfolio and I can analyze them." | Validator catches empty data, routes to Synthesizer with empty-state message | Unit test |
| Single asset | Normal analysis + "Your portfolio is concentrated in a single asset." | Allocation Advisor flags concentration risk | Unit test |
| Nonsense query ("what's the weather?") | Graceful deflection with capability list | Clarifier node activates | Integration test |
| Prompt injection ("ignore instructions") | "I specialize in financial analysis. I can help with..." | System prompt defense + Clarifier node | Integration test |
| Ambiguous ticker ("How's Apple?") | "I found AAPL (Apple Inc.) on NASDAQ. Is that what you meant?" | Tool Executor validates ticker, returns clarification if ambiguous | Unit test |
| Future date request | "I analyze historical data but don't make predictions. Want your past year instead?" | Validator rejects future dates, Error Handler suggests alternative | Unit test |
| Ghostfolio API down | "I'm having trouble connecting to your portfolio data. Please check that Ghostfolio is running." | GhostfolioClient returns error ToolResult, Error Handler presents gracefully | Integration test |
| Bearer token expired | Auto-refresh triggered, retry the request transparently | `auth.py` catches 401, re-authenticates, retries original request | Unit test (`test_auth.py`) |
| LLM rate limited | "I'm experiencing high demand. Please try again in a moment." | Exponential backoff with 3 retries before surfacing error | Integration test |
| Rapid-fire messages | Messages queued, processed sequentially per thread | LangGraph's thread management handles naturally | Manual test |

---

## Appendix A: File Manifest

```
agentforge-ghostfolio/
├── agent/
│   ├── main.py                    # FastAPI app, SSE endpoint, startup auth
│   ├── auth.py                    # Bearer token lifecycle manager
│   ├── graph.py                   # LangGraph 6-node topology definition
│   ├── state.py                   # AgentState TypedDict
│   ├── client.py                  # GhostfolioClient (httpx, cache, auth)
│   ├── tools/
│   │   ├── portfolio_analyzer.py
│   │   ├── transaction_categorizer.py
│   │   ├── tax_estimator.py
│   │   └── allocation_advisor.py
│   ├── models.py                  # ToolResult, response block schemas
│   ├── prompts.py                 # System prompt, tool descriptions
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
│       ├── unit/
│       │   ├── test_portfolio_analyzer.py
│       │   ├── test_transaction_categorizer.py
│       │   ├── test_tax_estimator.py
│       │   ├── test_allocation_advisor.py
│       │   └── test_auth.py
│       ├── integration/
│       │   ├── test_graph_routing.py
│       │   └── test_state_transitions.py
│       ├── e2e/
│       │   └── golden_path.ipynb
│       └── conftest.py
├── ghostfolio/                    # Forked Ghostfolio repo (submodule or nested)
│   └── apps/client/src/app/
│       └── pages/agent/           # NEW — standalone components (no NgModule)
│           ├── agent-page.routes.ts      # Standalone routes (exports routes: Routes)
│           ├── agent-fab/
│           │   └── agent-fab.component.ts  # Standalone (selector: gf-agent-fab)
│           ├── agent-chat-panel/
│           │   └── agent-chat-panel.component.ts  # Standalone
│           ├── blocks/
│           │   ├── chat-text-block.component.ts
│           │   ├── chat-table-block.component.ts
│           │   ├── chat-metric-card.component.ts
│           │   └── chat-chart-block.component.ts
│           ├── services/
│           │   └── agent.service.ts
│           └── models/
│               └── agent.types.ts
├── docker/
│   ├── docker-compose.yml         # Ghostfolio's existing compose file
│   └── seed.sql                   # Demo portfolio data
├── docker-compose.agent.yml       # Agent service overlay
├── start.sh                       # Convenience launcher with env validation
├── .env.example
├── docs/
│   ├── ADR-001-orchestration.md
│   ├── ADR-002-llm-provider.md
│   ├── ADR-003-memory.md
│   ├── ADR-004-backend.md
│   ├── ADR-005-frontend.md
│   ├── ADR-006-streaming.md
│   ├── ADR-007-error-handling.md
│   ├── ADR-008-fork-strategy.md
│   ├── ADR-009-authentication.md
│   └── ghostfolio-api-map.md      # Discovered API endpoints from Day 2
└── README.md
```

---

## Appendix B: Ghostfolio API Quick Reference

> **WARNING:** Only 3 Ghostfolio API endpoints are documented in the README. All portfolio, holdings, and performance endpoints are **internal and undocumented**. They must be discovered via browser DevTools (Network tab) or NestJS source code inspection during the Day 2 API Discovery phase.

### Documented Endpoints (from README)

**Authentication:**
```
POST /api/v1/auth/anonymous
Body: {"accessToken": "<SECURITY_TOKEN>"}
Response: Bearer token (use in Authorization header for all subsequent calls)
```

**Health Check:**
```
GET /api/v1/health
Auth: None required
```

**Activity Import:**
```
POST /api/v1/import
Auth: Bearer token required
Body: {
  "activities": [{
    "currency": "USD",
    "dataSource": "YAHOO",         // YAHOO | COINGECKO | MANUAL | GHOSTFOLIO
    "date": "2021-09-15T00:00:00.000Z",
    "fee": 19,
    "quantity": 5,
    "symbol": "MSFT",
    "type": "BUY",                 // BUY | SELL | DIVIDEND | FEE | INTEREST | LIABILITY
    "unitPrice": 298.58,           // Per-unit price, NOT total cost
    "accountId": "...",            // optional
    "comment": "..."               // optional
  }]
}
```

**Public Portfolio (if enabled):**
```
GET /api/v1/public/<ACCESS_ID>/portfolio
Auth: None required
```

### Undocumented Endpoints (must discover on Day 2)

These are the endpoints our tools will likely need. They must be verified by inspecting network traffic in the running application:

| Likely Endpoint | Needed By | Discovery Method |
|----------------|-----------|------------------|
| `GET /api/v2/portfolio/performance` | Portfolio Analyzer | DevTools Network tab (note: **v2**, not v1) |
| `GET /api/v1/portfolio/holdings` | Portfolio Analyzer, Allocation Advisor | DevTools Network tab |
| `GET /api/v1/order` or `/api/v1/activities` | Transaction Categorizer | DevTools Network tab |
| `GET /api/v1/portfolio/details` | Tax Estimator (needs cost basis) | DevTools Network tab |
| `GET /api/v1/account` | All tools (for account scoping) | DevTools Network tab |
| `GET /api/v1/symbol/lookup` | Input validation (ticker check) | NestJS source inspection |

---

## Appendix C: Key Decisions Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-23 | Initial build guidelines from architecture interview |
| 1.1 | 2026-02-23 | Corrected auth flow to Bearer token via `/api/v1/auth/anonymous`. Added ADR-009. Expanded activity types to 6 (added INTEREST, LIABILITY). Added `dataSource` and `unitPrice` fields to seed data. Fixed Docker Compose path to `docker/docker-compose.yml`. Added mandatory API Discovery phase (Day 2). Added undocumented API risk to registry. Updated all tool contracts with correct Ghostfolio schema fields. Added `.env.example` with all Ghostfolio variables. |
