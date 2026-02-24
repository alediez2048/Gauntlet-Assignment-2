# Claude Code — Best Practices & Guide for AgentForge

**Project:** Ghostfolio + AI Agent Integration  
**Purpose:** Reference for using Claude Code (CLI) effectively on this polyglot monorepo  
**Last Updated:** Feb 24, 2026

---

## Table of Contents

- [CLAUDE.md Setup](#claudemd-setup)
- [Project-Specific Context Loading](#project-specific-context-loading)
- [Recommended Workflows by Task Type](#recommended-workflows-by-task-type)
- [When to Use Claude Code vs Cursor](#when-to-use-claude-code-vs-cursor)
- [Useful Commands & Patterns](#useful-commands--patterns)
- [Working with This Polyglot Repo](#working-with-this-polyglot-repo)
- [Testing Workflows](#testing-workflows)
- [Docker Workflows](#docker-workflows)
- [Common Pitfalls & How to Avoid Them](#common-pitfalls--how-to-avoid-them)
- [Prompt Templates for Common Tasks](#prompt-templates-for-common-tasks)

---

## CLAUDE.md Setup

Claude Code reads a `CLAUDE.md` file at the repo root for persistent project context. Create one that encodes the critical knowledge from our indexing work.

### Recommended CLAUDE.md

```markdown
# AgentForge — Ghostfolio + AI Agent Integration

## Project Overview
Monorepo combining a forked Ghostfolio (Nx/Angular/NestJS) wealth management app
with a Python FastAPI + LangGraph AI agent sidecar. The agent provides portfolio
analysis, transaction categorization, tax estimation (FIFO), and allocation advice
through a floating chat widget.

## Architecture
- Frontend: Angular 21 (standalone components, Angular Material) at :4200 (dev) / :3333 (prod)
- Backend: NestJS 11 + Prisma 6 + PostgreSQL 15 + Redis 7 at :3333
- Agent: Python FastAPI + LangGraph + GPT-4o at :8000
- Communication: SSE streaming from agent to Angular client
- Auth: Bearer token via POST /api/v1/auth/anonymous

## Critical Facts
- Angular uses standalone components (bootstrapApplication), NOT NgModules
- Portfolio performance endpoint is GET /api/v2/portfolio/performance (v2, not v1)
- DateRange values are lowercase: "1d", "wtd", "mtd", "ytd", "1y", "5y", "max"
- Node.js >=22.18.0 required
- Ghostfolio pre-computes allocationInPercentage per holding
- dataSource is optional for FEE, INTEREST, LIABILITY activity types
- JWT expires in 180 days

## Directory Layout
- apps/api/src/ — NestJS backend (DO NOT modify unless necessary)
- apps/client/src/app/ — Angular frontend
- apps/client/src/app/pages/agent/ — NEW agent chat widget
- agent/ — NEW Python FastAPI + LangGraph service
- agent/tools/ — 4 pure-function tools
- agent/graph/ — LangGraph 6-node topology
- agent/clients/ — GhostfolioClient (httpx)
- agent/tests/ — pytest (unit, integration, e2e)
- libs/common/src/lib/ — Shared DTOs, interfaces, enums
- libs/ui/src/lib/ — Reusable Angular UI components
- docker/ — Docker Compose files
- prisma/ — PostgreSQL schema
- docs/ — requirements, architecture, tickets, reference

## Path Aliases (TypeScript)
- @ghostfolio/api/* → apps/api/src/*
- @ghostfolio/client/* → apps/client/src/app/*
- @ghostfolio/common/* → libs/common/src/lib/*
- @ghostfolio/ui/* → libs/ui/src/lib/*

## Fork Discipline
- ALL agent code goes in NEW files
- Only 3 existing files may be touched: app.routes.ts, app.component.ts, app.component.html
- Use gf-agent- prefix for new Angular component selectors

## Commands
- Dev server: npm run start:server && npm run start:client
- Dev DB: docker compose -f docker/docker-compose.dev.yml up -d
- DB setup: npm run database:setup
- Tests (JS): npm test
- Tests (Python): cd agent && pytest
- Full stack: docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml up -d
- Agent only: cd agent && uvicorn main:app --reload --port 8000

## Key Docs
- docs/requirements/AgentForge_PRD.md — Full task breakdown
- docs/architecture/AgentForge_Build_Guidelines.md — ADRs, contracts, topology
- docs/tickets/devlog.md — Development log (update after every ticket)
```

Place this at the repo root as `CLAUDE.md`. Claude Code will automatically read it at the start of every session.

### Subdirectory CLAUDE.md Files

For deeper context in specific areas, add scoped files:

**`agent/CLAUDE.md`:**
```markdown
# Agent Service

Python FastAPI + LangGraph agent. All tools are pure functions returning ToolResult.

## Tool Pattern
- Accept api_client: GhostfolioClient as first param (dependency injection)
- Always return ToolResult.ok() or ToolResult.fail() — never raise exceptions
- Validate inputs before calling the API
- Include metadata in ToolResult (response_time, cache_hit)

## Testing
- pytest with respx for HTTP mocking
- 3 tests per tool minimum: happy path, invalid input, API error
- Fixtures in tests/fixtures/ must match real Ghostfolio API response shapes
- No LLM calls in unit tests

## Key Dependencies
- langgraph for agent orchestration
- langchain-openai for GPT-4o
- httpx for async HTTP to Ghostfolio
- cachetools for 60s TTL API response cache
- pydantic for request/response validation
```

**`apps/client/src/app/pages/agent/CLAUDE.md`:**
```markdown
# Agent Chat Widget

Angular standalone components for the AI chat interface.

## Conventions
- Standalone components only (no NgModules)
- Selectors: gf-agent-* prefix
- Class names: Gf* prefix (e.g., GfAgentFabComponent)
- Use Angular Material components from Ghostfolio's design system
- Use ChangeDetectionStrategy.OnPush
- SSE consumption via fetch + getReader (not EventSource)
- Theme: respect --gf-theme-* CSS variables and .theme-dark class
```

---

## Project-Specific Context Loading

### Starting a Session

When starting Claude Code on this project, front-load context efficiently:

```bash
# Start with the primer for the current ticket
claude "Read docs/tickets/TICKET-01-primer.md and begin working on the deliverables"

# Or resume from the devlog
claude "Read docs/tickets/devlog.md to see what's been completed, then continue with the next pending ticket"
```

### Loading Context for Specific Areas

```bash
# Agent Python work
claude "Read agent/CLAUDE.md and the cursor rules in .cursor/rules/agent-patterns.mdc and .cursor/rules/python-code-style.mdc, then implement the portfolio analyzer tool"

# Angular frontend work
claude "Read .cursor/rules/angular-conventions.mdc and apps/client/src/app/app.component.ts to understand the app shell, then build the agent FAB component"

# Understanding Ghostfolio API
claude "Read .cursor/rules/ghostfolio-integration.mdc and apps/api/src/app/portfolio/portfolio.controller.ts to understand the portfolio endpoints"
```

---

## Recommended Workflows by Task Type

### 1. Python Tool Development (agent/tools/)

```bash
# Best approach: TDD with fixture-first development
claude "
1. Read agent/tests/fixtures/portfolio_performance.json for the expected API response shape
2. Write the test file agent/tests/unit/test_portfolio_analyzer.py with 3 tests
3. Run pytest to confirm tests fail
4. Implement agent/tools/portfolio_analyzer.py to make them pass
5. Run pytest to confirm all pass
"
```

### 2. LangGraph Topology (agent/graph/)

```bash
# Graph work benefits from seeing the full picture
claude "
Read docs/architecture/AgentForge_Build_Guidelines.md sections 3 (LangGraph Topology)
and 4 (Tool Contracts), then implement the 6-node graph in agent/graph/graph.py
with Router, Tool Executor, Validator, Synthesizer, Clarifier, and Error Handler nodes.
Use the AgentState from agent/graph/state.py.
"
```

### 3. Angular Component Development

```bash
# Always read the existing patterns first
claude "
Look at how apps/client/src/app/pages/accounts/accounts-page.routes.ts structures
its routes, then create the equivalent for the agent page at
apps/client/src/app/pages/agent/agent-page.routes.ts using the same standalone pattern.
"
```

### 4. Docker / Infrastructure

```bash
# Docker work benefits from seeing the existing compose files
claude "
Read docker/docker-compose.yml and docker/docker-compose.dev.yml,
then create docker/docker-compose.agent.yml as an overlay that adds the agent service
with health checks and depends_on ghostfolio.
"
```

### 5. Integration Testing

```bash
# Use Claude Code to run the full stack and test
claude "
Start the Docker stack with docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml up -d,
wait for all health checks to pass,
then test: curl the agent health endpoint, authenticate with Ghostfolio,
and call GET /api/v2/portfolio/performance with the Bearer token.
"
```

---

## When to Use Claude Code vs Cursor

| Task | Claude Code (CLI) | Cursor (IDE) |
|------|-------------------|--------------|
| Multi-file scaffolding (create 15+ files) | Excellent — faster file creation | Good but more clicks |
| Running shell commands (Docker, pytest, curl) | Excellent — native shell | Good via terminal |
| Debugging test failures | Good — can run + fix iteratively | Better — sees linter errors live |
| Editing existing Angular components | Fine | Better — has type checking, imports |
| Writing Python tools with tests | Excellent — TDD loop is natural | Excellent |
| Git operations (branch, commit, PR) | Excellent — native git | Good via terminal |
| Reading large files for context | Good | Better — can jump to definitions |
| Refactoring across many files | Excellent | Excellent |
| Exploring unfamiliar code | Good | Better — go-to-definition, hover |

### Recommended Split

- **Use Cursor** for: Angular UI work (type checking matters), editing existing Ghostfolio files, interactive debugging, exploring unfamiliar code
- **Use Claude Code** for: Python agent development (TDD loops), Docker/infra work, git operations, scaffolding, running test suites, seed data creation, multi-file changes

### Handoff Between Tools

Both tools can read the same context files. To hand off:

1. Update `docs/tickets/devlog.md` with what was done
2. The other tool reads the devlog to pick up where you left off
3. Cursor rules in `.cursor/rules/` work for Cursor; `CLAUDE.md` works for Claude Code
4. The primer files (`docs/tickets/TICKET-XX-primer.md`) work for both

---

## Useful Commands & Patterns

### Session Management

```bash
# Start a focused session
claude --print "Summarize the current state from docs/tickets/devlog.md"

# Continue from where you left off
claude --continue

# Run a single task without conversation
claude --print "Run pytest in agent/ and report results"
```

### Multi-File Operations

```bash
# Scaffold an entire tool with tests
claude "Create agent/tools/portfolio_analyzer.py and agent/tests/unit/test_portfolio_analyzer.py following the ToolResult pattern in agent/tools/base.py"

# Batch create fixture files
claude "Read the portfolio controller response types in libs/common/src/lib/interfaces/ and create matching JSON fixture files in agent/tests/fixtures/"
```

### Git Workflow

```bash
# Create feature branch and work
claude "Create branch feat/ticket-02-ghostfolio-client, implement the GhostfolioClient class, run tests, and commit with a conventional commit message"

# Review before committing
claude "Show me a git diff of all changes, explain each file, then commit with message 'feat: add GhostfolioClient with Bearer token auth'"
```

### Docker Operations

```bash
# Full stack management
claude "docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml up --build -d && sleep 30 && curl http://localhost:8000/health && curl http://localhost:3333/api/v1/health"

# View agent logs
claude "docker logs gf-agent --tail 50"

# Rebuild just the agent
claude "docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml up --build agent -d"
```

---

## Working with This Polyglot Repo

### Python (agent/)

- Use `async/await` throughout — httpx AsyncClient, FastAPI async endpoints
- Type hints on everything — Claude Code is good at inferring these
- `ToolResult` is the universal return type for tools
- Test with `pytest -xvs` for verbose output with print statements

### TypeScript/Angular (apps/client/)

- Standalone components only — if Claude Code generates an NgModule, reject it
- Import Angular Material modules in component `imports` arrays, not in a shared module
- Use `ChangeDetectionStrategy.OnPush` on all new components
- Follow Ghostfolio's naming: `GfXxxComponent`, selector `gf-xxx`

### NestJS (apps/api/) — Read Only

- Controllers are in `apps/api/src/app/` organized by feature
- Decorators: `@Controller('path')`, `@Get()`, `@Post()`, `@UseGuards(AuthGuard('jwt'))`
- Response types defined in `libs/common/src/lib/interfaces/`
- Don't modify these files — read them to understand the API

### Prisma (prisma/)

- Schema at `prisma/schema.prisma` — read for data model understanding
- Key models: User, Order (activities), Account, SymbolProfile, MarketData
- Key enums: Type (6 activity types), AssetClass, DataSource, DateRange

---

## Testing Workflows

### Python Agent Tests

```bash
# Run all agent tests
cd agent && pytest -xvs

# Run a specific test file
cd agent && pytest tests/unit/test_portfolio_analyzer.py -xvs

# Run with coverage
cd agent && pytest --cov=. --cov-report=term-missing

# Run only tests matching a pattern
cd agent && pytest -k "test_happy_path" -xvs
```

### Ghostfolio Tests (existing)

```bash
# Run all Ghostfolio tests
npm test

# Run specific workspace tests
npm run test:api
npm run test:common
npm run test:ui
```

### End-to-End Testing

```bash
# Authenticate and test an endpoint
TOKEN=$(curl -s -X POST http://localhost:3333/api/v1/auth/anonymous \
  -H "Content-Type: application/json" \
  -d '{"accessToken":"YOUR_TOKEN"}' | jq -r '.authToken')

curl -s http://localhost:3333/api/v2/portfolio/performance?range=ytd \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

## Docker Workflows

### Development Mode (Ghostfolio native + Docker DB)

```bash
# Start just Postgres + Redis
docker compose -f docker/docker-compose.dev.yml up -d

# Run Ghostfolio natively for hot reload
npm run start:server   # Terminal 1
npm run start:client   # Terminal 2

# Run agent natively for hot reload
cd agent && uvicorn main:app --reload --port 8000  # Terminal 3
```

### Full Docker Mode (all 4 services)

```bash
# Build and start everything
docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml up --build -d

# Check all services are healthy
docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml ps

# Tail agent logs
docker logs gf-agent -f

# Tear down everything (including volumes for clean state)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml down -v
```

### Seed Data Import

```bash
# After Ghostfolio is running and a user is created
TOKEN=$(curl -s -X POST http://localhost:3333/api/v1/auth/anonymous \
  -H "Content-Type: application/json" \
  -d '{"accessToken":"YOUR_TOKEN"}' | jq -r '.authToken')

curl -X POST http://localhost:3333/api/v1/import \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @docker/seed-data.json
```

---

## Common Pitfalls & How to Avoid Them

### 1. NgModule Generation

**Problem:** Claude generates `@NgModule` for Angular components.  
**Fix:** Explicitly say "standalone component" and reference `app.component.ts` as the pattern. Ghostfolio has zero NgModules.

### 2. Wrong API Version

**Problem:** Using `/api/v1/portfolio/performance` (returns 404).  
**Fix:** Performance is v2: `/api/v2/portfolio/performance`. All other portfolio endpoints are v1.

### 3. Uppercase DateRange

**Problem:** Using `"YTD"`, `"1Y"` (API doesn't recognize them).  
**Fix:** Always lowercase: `"ytd"`, `"1y"`, `"max"`.

### 4. Exceptions in Tools

**Problem:** Tool raises an exception which crashes the LangGraph agent.  
**Fix:** Always return `ToolResult.fail()` — never let exceptions escape tool functions.

### 5. Blocking HTTP in FastAPI

**Problem:** Using `requests` library (blocking) in an async FastAPI app.  
**Fix:** Always use `httpx.AsyncClient` with `await`.

### 6. Modifying Existing Ghostfolio Files

**Problem:** Editing existing controllers or components.  
**Fix:** All agent code goes in new files. Only 3 files get one-line changes (in the UI ticket, not now).

### 7. Docker Networking

**Problem:** Agent container can't reach Ghostfolio at `localhost:3333`.  
**Fix:** Inside Docker, use the service name: `http://ghostfolio:3333`. Set `GHOSTFOLIO_API_URL=http://ghostfolio:3333` in `.env`.

### 8. Node Version Mismatch

**Problem:** `npm install` fails with engine incompatibility.  
**Fix:** Ghostfolio requires Node >=22.18.0. Use `nvm use 22` or install the right version.

### 9. Missing Auth Token

**Problem:** Agent gets 401 from Ghostfolio API.  
**Fix:** The security token is the user's access token from Ghostfolio (visible in user settings), not the JWT. The agent must call `/api/v1/auth/anonymous` first to exchange it for a JWT.

### 10. Prisma Client Not Generated

**Problem:** TypeScript errors about missing Prisma types after `npm install`.  
**Fix:** Run `npx prisma generate` (or `npm run database:generate-typings`). The `postinstall` script should handle this automatically.

---

## Prompt Templates for Common Tasks

### Implementing a New Tool

```
Read agent/tools/base.py for the ToolResult contract and agent/tools/portfolio_analyzer.py
for the existing tool pattern. Then implement agent/tools/transaction_categorizer.py that:
1. Accepts api_client: GhostfolioClient and days_back: int = 90
2. Validates days_back is between 1 and 3650
3. Calls api_client.get_transactions() to fetch orders
4. Groups transactions by type (BUY, SELL, DIVIDEND, FEE, INTEREST, LIABILITY)
5. Computes summary stats (total invested, total dividends, total fees, most traded symbol)
6. Returns ToolResult.ok() with the categorized data
7. Returns ToolResult.fail() on any error without raising exceptions
Also write 3 tests in agent/tests/unit/test_transaction_categorizer.py.
```

### Building an Angular Component

```
Read apps/client/src/app/app.component.ts to see the standalone component pattern used
in this project. Then create a standalone Angular component at
apps/client/src/app/pages/agent/agent-fab/agent-fab.component.ts with:
- selector: gf-agent-fab
- A fixed-position FAB button (bottom-right, z-index 999) using mat-fab from Angular Material
- Click handler that toggles a chat panel open/closed
- Use ChangeDetectionStrategy.OnPush
- Include the .html and .scss files
- Follow Ghostfolio's existing FAB pattern (see apps/client/src/app/pages/portfolio/activities/)
```

### Debugging a Failing Test

```
Run `cd agent && pytest tests/unit/test_portfolio_analyzer.py -xvs` and show me the output.
If tests fail, read the test file and the implementation file, identify the mismatch,
fix the implementation (not the test unless the test has a bug), and re-run to confirm.
```

### Creating Seed Data

```
Read prisma/schema.prisma for the Order model and libs/common/src/lib/dtos/create-order.dto.ts
for the import format. Create a seed-data.json file with 50+ activities spanning 2 years,
covering all 6 types (BUY, SELL, DIVIDEND, FEE, INTEREST, LIABILITY), using YAHOO as
dataSource for stocks/ETFs, with realistic symbols (AAPL, MSFT, VTI, BND, etc.),
including both short-term and long-term holdings for tax calculation scenarios,
and an intentional tech overweight (~45%) for allocation advisor testing.
```

---

## Session Checklist

Before ending any Claude Code session:

- [ ] All tests pass (`pytest` for Python, `npm test` for JS if changed)
- [ ] No uncommitted changes (or explicitly staged for review)
- [ ] `docs/tickets/devlog.md` updated with what was accomplished
- [ ] Any new files follow the naming conventions in cursor rules
- [ ] Docker stack still healthy if it was running
- [ ] Next ticket primer updated if scope changed
