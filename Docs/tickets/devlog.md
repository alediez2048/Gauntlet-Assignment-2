# AgentForge — Development Log

**Project:** Ghostfolio + AI Agent Integration (AgentForge)  
**Sprint:** Feb 24 – Mar 2, 2026 (MVP) | Mar 2–7, 2026 (Production Polish)  
**Developer:** JAD  
**AI Assistant:** Claude (Cursor Agent)

---

## Timeline

| Phase | Days | Target |
|-------|------|--------|
| MVP | Feb 24–Mar 2 (6 days, ~8 hrs) | Working 2–4 tool agent with chat widget, Docker Compose |
| Production | Mar 2–7 (5 days) | Edge cases, polish, testing, demo prep |

---

## MVP Scope (TICKET-01 → TICKET-10)

The following tickets are **required** to reach MVP — a working end-to-end agent with functional tools, a chat UI, and a one-command Docker boot:

| Ticket | Title | MVP Role |
|--------|-------|----------|
| TICKET-01 | Environment Setup & Agent Scaffold | **Foundation** — nothing works without this |
| TICKET-02 | GhostfolioClient + Auth Module | **Foundation** — every tool depends on this |
| TICKET-03 | Portfolio Performance Analyzer | **Core tool** — minimum viable demo query |
| TICKET-04 | Transaction Categorizer | **Core tool** — second demo query |
| TICKET-05 | Capital Gains Tax Estimator | **Core tool** — demonstrates deterministic (non-LLM) logic |
| TICKET-06 | Asset Allocation Advisor | **Core tool** — demonstrates structured output (charts) |
| TICKET-07 | LangGraph 6-Node Graph + System Prompt | **Core** — the agent brain; routes queries to tools |
| TICKET-08 | FastAPI SSE Endpoint + Event Mapping | **Core** — connects agent to frontend via streaming |
| TICKET-09 | Angular Agent UI — FAB + Chat Panel | **Core** — the user-facing chat widget |
| TICKET-10 | Docker Compose + Seed Data + E2E | **Core** — one-command boot + demo data |

> **Minimum viable MVP:** If time is tight, TICKET-05 and TICKET-06 can be deferred to production phase (2 tools instead of 4). TICKET-01 through TICKET-04 + TICKET-07 through TICKET-10 constitute the absolute minimum.

**Post-MVP / Production Polish (TICKET-11 → TICKET-12):**

| Ticket | Title | Role |
|--------|-------|------|
| TICKET-11 | Edge Case Hardening + Golden Path E2E | Polish — adversarial testing, robustness |
| TICKET-12 | README + Demo Script + Rehearsal | Polish — documentation, demo prep, rehearsals |

---

## Entry Format Template

Each ticket entry follows this standardized structure:

```
## TICKET-XX: [Title] [Status Emoji]

### 🧠 Plain-English Summary
- What was done
- What it means
- Success looked like
- How it works (simple)

### 📋 Metadata
- Status, Date, Time (vs Estimate), Branch, Commit

### 🎯 Scope
- What was planned/built

### 🏆 Key Achievements
- Notable accomplishments and highlights

### 🔧 Technical Implementation
- Architecture decisions, code patterns, infrastructure

### ⚠️ Issues & Solutions
- Problems encountered and fixes applied

### ✅ Testing
- Automated and manual test results

### 📁 Files Changed
- Created and modified files

### 🎯 Acceptance Criteria
- PRD requirements checklist

### 📊 Performance
- Metrics, benchmarks, observations

### 🚀 Next Steps
- What comes next

### 💡 Learnings
- Key takeaways and insights
```

---

## Phase 0: Pre-Development Setup

---

## TICKET-00: Repository Indexing & Docs Alignment 🟢

### 🧠 Plain-English Summary
- **What was done:** Deep-indexed the entire Ghostfolio forked repo and all 5 AgentForge planning docs. Cross-referenced docs against the real codebase and corrected every inaccuracy.
- **What it means:** We have a verified, single source of truth — the docs now match the actual code exactly. No surprises during implementation.
- **Success looked like:** Every API endpoint, Angular pattern, auth flow, and Docker config referenced in the docs was validated against the actual source code.
- **How it works (simple):** Read every controller, route file, Prisma schema, Docker config, and Angular component. Found 6 categories of corrections and applied them across 4 doc files.

### 📋 Metadata
- **Status:** Complete
- **Completed:** Feb 24, 2026
- **Time Spent:** ~1.5 hours
- **Branch:** `main`

### 🎯 Scope
- ✅ Full Ghostfolio repo indexed (apps/api, apps/client, libs/common, libs/ui, prisma, docker)
- ✅ All 5 docs indexed (PRD, Build Guidelines, PreSearch Checklist, Interview, Week 2 materials)
- ✅ Cross-referenced docs against actual codebase
- ✅ Applied all corrections directly to doc files
- ✅ Created 10 Cursor rules files for development guidance

### 🏆 Key Achievements
- **6 Correction Categories Identified & Fixed:**
  1. Angular uses standalone components (`app.routes.ts`), not NgModules (`app-routing.module.ts`)
  2. Performance endpoint is `GET /api/v2/portfolio/performance` (v2, not v1)
  3. DateRange values are lowercase (`"1d"`, `"ytd"`, `"max"`, not `"Today"`, `"YTD"`, `"Max"`)
  4. Node.js requirement is >=22.18.0 (not 18+)
  5. `dataSource` is optional for FEE/INTEREST/LIABILITY activity types
  6. Ghostfolio pre-computes `allocationInPercentage` per holding — no need to recalculate
- **10 Cursor Rules Created** covering project structure, tech stack, agent patterns, Ghostfolio integration, TDD, Angular conventions, Docker, error handling, Python style, and SSE streaming

### 🔧 Technical Implementation

**Key Codebase Discoveries:**
- Auth: `POST /api/v1/auth/anonymous` → hashes token with HMAC-SHA512 → signs JWT (180-day expiry)
- App bootstrap: `bootstrapApplication(GfAppComponent)` — fully standalone, no root NgModule
- App shell: `<header>` → `<main><router-outlet /></main>` → `<footer>` (53 lines total)
- Portfolio controller: 8 endpoints, performance is @Version('2'), details/holdings are v1
- Order controller: full CRUD, returns `{activities: Activity[], count: number}`
- Import endpoint: accepts `{activities: CreateOrderDto[]}` with optional accounts, tags, assetProfiles
- Prisma Type enum: BUY, SELL, DIVIDEND, FEE, INTEREST, LIABILITY (6 types confirmed)
- AssetClass enum: EQUITY, FIXED_INCOME, LIQUIDITY, COMMODITY, REAL_ESTATE, ALTERNATIVE_INVESTMENT
- DateRange type: `"1d" | "1y" | "5y" | "max" | "mtd" | "wtd" | "ytd" | string`
- Docker: 3-service compose (postgres:15, redis:alpine, ghostfolio), dev compose extends with port exposure
- FAB pattern in codebase: `position: fixed; bottom: 2rem; right: 2rem; z-index: 999`

**Docs Corrected:**
- `AgentForge_PRD.md` — 8 corrections (routing, module, date ranges, Node version, file manifest, dataSource, allocation)
- `AgentForge_Build_Guidelines.md` — 6 corrections (routing, module, endpoint v2, date ranges, tool contracts, file manifest)
- `AgentForge_Interview_Complete.md` — 3 corrections (routing, module, endpoint v2, date ranges)
- `AgentForge_PreSearch_Checklist.md` — 1 correction (endpoint v2)

### ⚠️ Issues & Solutions

| Issue | Solution |
|-------|----------|
| Docs referenced `app-routing.module.ts` (NgModule) | Corrected to `app.routes.ts` (standalone routes) across all 4 docs |
| Docs referenced `agent.module.ts` NgModule pattern | Corrected to standalone components with `agent-page.routes.ts` |
| Performance endpoint listed as v1 | Corrected to v2 (`@Version('2')` in controller) |
| Date ranges listed as uppercase (`"YTD"`, `"1Y"`) | Corrected to lowercase (`"ytd"`, `"1y"`) matching actual `DateRange` type |
| Node.js listed as 18+ | Corrected to 22+ (>=22.18.0 per `package.json` engines) |
| File manifest showed 2 modified files | Corrected to 3 (added `app.component.ts` for standalone imports) |

### ✅ Testing
- ✅ Verified all `agent.module.ts` / `AgentModule` references removed from docs (grep: 0 matches)
- ✅ Verified all `/api/v1/portfolio/performance` references removed (grep: 0 matches)
- ✅ Verified all `Node.js 18` references removed (grep: 0 matches)
- ✅ Verified all uppercase date range references removed (grep: 0 matches)
- ✅ Verified remaining `app-routing.module.ts` mention is only in "not this" context

### 📁 Files Changed

**Created:**
- `.cursor/rules/project-structure.mdc`
- `.cursor/rules/tech-stack.mdc`
- `.cursor/rules/agent-patterns.mdc`
- `.cursor/rules/ghostfolio-integration.mdc`
- `.cursor/rules/tdd-methodology.mdc`
- `.cursor/rules/angular-conventions.mdc`
- `.cursor/rules/docker-infrastructure.mdc`
- `.cursor/rules/error-handling.mdc`
- `.cursor/rules/python-code-style.mdc`
- `.cursor/rules/sse-streaming.mdc`

**Modified:**
- `docs/AgentForge_PRD.md` — 8 corrections
- `docs/AgentForge_Build_Guidelines.md` — 6 corrections
- `docs/AgentForge_Interview_Complete.md` — 3 corrections
- `docs/AgentForge_PreSearch_Checklist.md` — 1 correction

### 🎯 Acceptance Criteria
- ✅ Full repo structure understood and documented
- ✅ All 5 planning docs indexed and internalized
- ✅ Docs cross-referenced against actual codebase
- ✅ All inaccuracies corrected directly in doc files
- ✅ Cursor rules created for development guidance
- ✅ API endpoints mapped for all 4 agent tools

### 📊 Performance
- Indexed ~2,000+ files across the Nx monorepo
- Examined 15+ controllers, 10+ interfaces, full Prisma schema
- 18 total corrections applied across 4 documents
- 10 cursor rules created (~18KB total)

### 🚀 Next Steps (TICKET-01)
- Set up local environment (`.env` from `.env.dev`, Docker Compose for Postgres + Redis)
- Verify Ghostfolio builds and runs locally (`npm install`, `npm run database:setup`, `npm run start:server`)
- Create first admin user via "Get Started"
- Scaffold the `/agent` Python service directory
- Create `requirements.txt` with pinned dependencies
- Create agent `Dockerfile`

### 💡 Learnings
1. **Ghostfolio is fully standalone Angular** — no NgModules anywhere, which simplifies our agent UI integration
2. **Performance endpoint is v2** — easy to miss since all other portfolio endpoints are v1
3. **DateRange is lowercase** — the README shows uppercase (`YTD`, `1Y`) but the actual TypeScript type and API use lowercase
4. **Allocation is pre-computed** — `allocationInPercentage`, `assetClass`, `assetSubClass` come from the API, saving us computation work
5. **JWT lasts 180 days** — no need for aggressive token refresh in a demo context, but still good to implement refresh-on-401
6. **Import DTO is flexible** — `dataSource` optional for FEE/INTEREST/LIABILITY simplifies seed data creation

**Time Variance:** On estimate — indexing and correction was thorough but efficient

---

## Phase 1: Environment Setup & Agent Scaffold

---

## TICKET-01: Environment Setup & Agent Scaffold ⬜ `MVP`

> **Planned scope:** Local environment running, agent service scaffolded, Docker Compose overlay created

---

## Phase 2: Tool Development

---

## TICKET-02: GhostfolioClient + Auth Module ⬜ `MVP`

> **Planned scope:** HTTP client with Bearer token auth, MockClient, test fixtures, auth tests

---

## TICKET-03: Tool 1 — Portfolio Performance Analyzer ⬜ `MVP`

> **Planned scope:** Pure function tool, 3+ unit tests, validated against live Ghostfolio

---

## TICKET-04: Tool 2 — Transaction Categorizer ⬜ `MVP`

> **Planned scope:** Categorize by 6 activity types, summary stats, 3+ unit tests

---

## TICKET-05: Tool 3 — Capital Gains Tax Estimator ⬜ `MVP — deferrable if time-constrained`

> **Planned scope:** FIFO cost basis algorithm, short/long-term classification, hand-verified tests

---

## TICKET-06: Tool 4 — Asset Allocation Advisor ⬜ `MVP — deferrable if time-constrained`

> **Planned scope:** Current vs target allocation, concentration warnings, 3+ unit tests

---

## Phase 3: LangGraph Agent Core

---

## TICKET-07: LangGraph 6-Node Graph + System Prompt ⬜ `MVP`

> **Planned scope:** Router, Tool Executor, Validator, Synthesizer, Clarifier, Error Handler, routing tests

---

## Phase 4: Streaming & Backend API

---

## TICKET-08: FastAPI SSE Endpoint + Event Mapping ⬜ `MVP`

> **Planned scope:** POST /api/agent/chat, SSE streaming, event type mapping, CORS, health check

---

## Phase 5: Angular Chat Widget

---

## TICKET-09: Angular Agent UI — FAB + Chat Panel ⬜ `MVP`

> **Planned scope:** Standalone components, FAB overlay, chat panel, AgentService, block renderers

---

## Phase 6: Docker & Integration

---

## TICKET-10: Docker Compose + Seed Data + E2E ⬜ `MVP`

> **Planned scope:** docker-compose.agent.yml, seed portfolio, full-stack boot, 5-query E2E test

---

## Phase 7: Testing & Edge Cases

---

## TICKET-11: Edge Case Hardening + Golden Path E2E ⬜ `POST-MVP`

> **Planned scope:** Empty portfolio, nonsense query, prompt injection, ambiguous ticker, rapid-fire, backup video

---

## Phase 8: Demo Preparation

---

## TICKET-12: README + Demo Script + Rehearsal ⬜ `POST-MVP`

> **Planned scope:** Architecture diagram, quick start, tools table, demo GIF, 3 rehearsal runs

---

## Status Legend

| Emoji | Meaning |
|-------|---------|
| ⬜ | Not started |
| 🔵 | In progress |
| 🟢 | Complete |
| 🔴 | Blocked |
| ⚠️ | Complete with issues |

---

## Running Totals

| Metric | Value |
|--------|-------|
| Tickets Complete | 1 / 13 |
| Total Dev Time | ~1.5 hrs |
| Tests Passing | — |
| Files Created | 10 |
| Files Modified | 4 |
| Cursor Rules | 10 |
