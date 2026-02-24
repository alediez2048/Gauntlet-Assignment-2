# TICKET-01 Primer: Environment Setup & Agent Scaffold

**For:** New Cursor Agent session  
**Project:** AgentForge — Ghostfolio + AI Agent Integration  
**Date:** Feb 24, 2026  
**Previous work:** TICKET-00 (repo indexing, doc corrections, cursor rules) — see `docs/tickets/devlog.md`

---

## What Is This Project?

We're adding an **AI financial analyst agent** to [Ghostfolio](https://ghostfol.io), an open-source wealth management app. The agent lives as a **Python FastAPI sidecar** that communicates with Ghostfolio's REST API, powered by **LangGraph + GPT-4o**, with a **floating chat widget** in the Angular frontend.

### Key Architecture

```
Browser (Angular) → SSE → FastAPI Agent (:8000) → Ghostfolio API (:3333) → PostgreSQL + Redis
```

4 tools: Portfolio Analyzer, Transaction Categorizer, Tax Estimator (FIFO), Allocation Advisor.

---

## What Was Already Done (TICKET-00)

- Full repo indexed (NestJS controllers, Angular components, Prisma schema, Docker configs)
- All 5 planning docs cross-referenced against the real codebase
- 18 corrections applied to docs (routing patterns, API versions, date ranges, Node version)
- 10 Cursor rules created in `.cursor/rules/` — **read these first, they encode all conventions**
- Docs organized into `docs/requirements/`, `docs/architecture/`, `docs/tickets/`, `docs/reference/`

### Critical Findings From Indexing (Must Know)

1. **Angular is standalone** — `bootstrapApplication()`, no NgModules. Routes in `app.routes.ts`, not `app-routing.module.ts`
2. **Performance endpoint is v2** — `GET /api/v2/portfolio/performance` (all other portfolio endpoints are v1)
3. **DateRange values are lowercase** — `"1d"`, `"wtd"`, `"mtd"`, `"ytd"`, `"1y"`, `"5y"`, `"max"`
4. **Auth flow** — `POST /api/v1/auth/anonymous` with `{"accessToken": "<token>"}` → returns `{"authToken": "<jwt>"}` (180-day expiry)
5. **Node.js >=22.18.0** required (not 18)
6. **Ghostfolio pre-computes** `allocationInPercentage`, `assetClass`, `assetSubClass` per holding

---

## What TICKET-01 Must Accomplish

### Goal

Get the local development environment fully running and scaffold the agent service directory so that tool development (TICKET-02+) can begin immediately.

### Deliverables Checklist

#### A. Local Ghostfolio Running

- [ ] Copy `.env.dev` to `.env`, populate with real values (generate salts with `openssl rand -hex 32`)
- [ ] Start Postgres + Redis: `docker compose -f docker/docker-compose.dev.yml up -d`
- [ ] Run `npm install` (requires Node >=22.18.0)
- [ ] Run `npm run database:setup` (pushes Prisma schema + seeds)
- [ ] Start the server: `npm run start:server`
- [ ] Start the client: `npm run start:client`
- [ ] Open `https://localhost:4200/en` → create first user via "Get Started" (gets ADMIN role)
- [ ] Verify the app works: navigate dashboard, add a test holding

#### B. Agent Service Scaffold

- [ ] Create `/agent` directory at repo root with this structure:

```
agent/
├── main.py                    # FastAPI app skeleton (health endpoint only for now)
├── auth.py                    # Placeholder module for Bearer token lifecycle
├── requirements.txt           # Pinned Python dependencies
├── Dockerfile                 # Python 3.11-slim, uvicorn CMD
├── clients/
│   ├── __init__.py
│   ├── ghostfolio_client.py   # Placeholder class
│   └── mock_client.py         # Placeholder class
├── tools/
│   ├── __init__.py
│   ├── base.py                # ToolResult dataclass
│   ├── portfolio_analyzer.py  # Placeholder
│   ├── transaction_categorizer.py
│   ├── tax_estimator.py
│   └── allocation_advisor.py
├── graph/
│   ├── __init__.py
│   ├── state.py               # AgentState TypedDict placeholder
│   ├── nodes.py               # Placeholder
│   └── graph.py               # Placeholder
├── prompts.py                 # Placeholder
└── tests/
    ├── __init__.py
    ├── conftest.py            # Shared fixtures
    ├── fixtures/              # JSON response fixtures (empty dir for now)
    ├── unit/
    │   └── __init__.py
    └── integration/
        └── __init__.py
```

- [ ] `requirements.txt` with these dependencies (use latest stable versions — do NOT make up version numbers, use `pip install` to get them):

```
langchain
langgraph
langchain-openai
fastapi
uvicorn[standard]
httpx
pytest
pytest-asyncio
respx
cachetools
pydantic
python-dotenv
```

- [ ] `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] `main.py` with minimal FastAPI app:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AgentForge", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3333", "http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] `tools/base.py` with ToolResult:

```python
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class ToolResult:
    success: bool
    data: Optional[dict[str, Any]]
    error: Optional[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, data: dict[str, Any], **meta: Any) -> "ToolResult":
        return cls(success=True, data=data, error=None, metadata=meta)

    @classmethod
    def fail(cls, error: str, **meta: Any) -> "ToolResult":
        return cls(success=False, data=None, error=error, metadata=meta)
```

#### C. Docker Compose Agent Overlay

- [ ] Create `docker/docker-compose.agent.yml`:

```yaml
services:
  agent:
    build:
      context: ../agent
      dockerfile: Dockerfile
    container_name: gf-agent
    restart: unless-stopped
    env_file:
      - ../.env
    ports:
      - 8000:8000
    depends_on:
      ghostfolio:
        condition: service_healthy
    healthcheck:
      test: ['CMD-SHELL', 'curl -f http://localhost:8000/health']
      interval: 10s
      timeout: 5s
      retries: 5
```

- [ ] Verify it works: `docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml up -d`
- [ ] Confirm `curl http://localhost:8000/health` returns `{"status": "ok"}`

#### D. Updated .env.example

- [ ] Add agent-specific variables to `.env.example`:

```env
# === Agent Service ===
OPENAI_API_KEY=<your-openai-api-key>
GHOSTFOLIO_API_URL=http://ghostfolio:3333
GHOSTFOLIO_ACCESS_TOKEN=<security-token-from-ghostfolio-user>
```

- [ ] Ensure `.env` is in `.gitignore` (it already is)

#### E. Verify Agent Talks to Ghostfolio

- [ ] With the full Docker stack running, exec into the agent container
- [ ] Verify the agent can reach Ghostfolio: `curl http://ghostfolio:3333/api/v1/health`
- [ ] This confirms Docker networking works for TICKET-02 (GhostfolioClient)

---

## Important Context

### Existing Files You Should NOT Modify

This is a forked repo. The fork discipline rule is: **all agent code goes in new files**. Only 3 existing files will be touched (in later tickets, not this one):

- `apps/client/src/app/app.routes.ts` — one route entry
- `apps/client/src/app/app.component.ts` — one import
- `apps/client/src/app/app.component.html` — one line

### Key Existing Files to Reference

| File | Why |
|------|-----|
| `.env.dev` | Template for local dev env vars (Postgres, Redis on localhost) |
| `.env.example` | Template for Docker Compose env vars (services on internal hostnames) |
| `docker/docker-compose.yml` | Existing 3-service compose (ghostfolio, postgres, redis) |
| `docker/docker-compose.dev.yml` | Dev compose (just postgres + redis with port exposure) |
| `package.json` | Node >=22.18.0, all npm scripts |
| `prisma/schema.prisma` | Full data model (User, Order, Account, SymbolProfile, etc.) |

### Cursor Rules (Already Created)

Read `.cursor/rules/` — these 11 files encode every convention:

- `project-structure.mdc` — directory layout, path aliases, fork discipline
- `tech-stack.mdc` — exact versions for everything
- `agent-patterns.mdc` — ToolResult, tool design, LangGraph topology
- `ghostfolio-integration.mdc` — auth flow, API endpoints, enums, import format
- `tdd-methodology.mdc` — 3-layer testing strategy
- `angular-conventions.mdc` — standalone components, Material, SSE consumption
- `docker-infrastructure.mdc` — 4-service compose, healthchecks, env vars
- `error-handling.mdc` — errors as values, validation gates, error taxonomy
- `python-code-style.mdc` — type hints, docstrings, import order
- `sse-streaming.mdc` — event types, SSE format, response blocks
- `devlog.mdc` — update devlog after every ticket

### Docs to Read If Needed

| Doc | Path | When to Read |
|-----|------|-------------|
| PRD (full task breakdown) | `docs/requirements/AgentForge_PRD.md` | For detailed task specs |
| Build Guidelines (ADRs, contracts) | `docs/architecture/AgentForge_Build_Guidelines.md` | For architecture decisions |
| DevLog | `docs/tickets/devlog.md` | To see what's been done and update after completion |

---

## Verified API Endpoints (From TICKET-00 Discovery)

These endpoints were verified by reading the actual NestJS controller source code:

| Endpoint | Version | Auth | Returns | Used By |
|----------|---------|------|---------|---------|
| `POST /api/v1/auth/anonymous` | v1 | No | `{authToken: string}` | Auth module |
| `GET /api/v1/health` | v1 | No | `{status: "OK"}` | Health checks |
| `GET /api/v2/portfolio/performance` | **v2** | Yes | Performance chart + metrics | Tool 1 |
| `GET /api/v1/portfolio/details` | v1 | Yes | Holdings map + summary | Tool 4 |
| `GET /api/v1/portfolio/holdings` | v1 | Yes | Holdings array | Tool 1, 4 |
| `GET /api/v1/order` | v1 | Yes | Activities + count | Tool 2, 3 |
| `GET /api/v1/portfolio/dividends` | v1 | Yes | Dividend activities | Tool 2 |
| `POST /api/v1/import` | v1 | Yes | Imported activities | Seed data |

Common query params: `range` (DateRange), `accounts`, `assetClasses`, `tags`, `sortColumn`, `sortDirection`

---

## Troubleshooting: `npm run start:server`

If the server starts but you see these, use the following.

### 1. Redis AUTH errors (spam in logs)

**Symptom:** `[RedisCacheService] ERR AUTH <password> called without any password configured for the default user`

**Cause:** The API sends `REDIS_PASSWORD` from `.env`, but the Redis you’re connecting to has no password.

**Fix (recommended for local dev):**

1. In `.env`, set `REDIS_PASSWORD=` (empty) so the API does not send AUTH.
2. The dev Compose file (`docker/docker-compose.dev.yml`) runs Redis **without** a password. Restart the dev stack so Redis is recreated with that config:
   ```bash
   cd docker && docker compose -f docker-compose.dev.yml down && docker compose -f docker-compose.dev.yml up -d
   ```
   (From repo root you can use `docker compose -f docker/docker-compose.dev.yml down` then `up -d`.)
3. Run `npm run start:server` again.

Redis AUTH and HTML errors should stop; the server will listen on http://0.0.0.0:3333.

### 2. HTMLTemplateMiddleware “Failed to initialize index HTML map”

**Symptom:** `ENOENT: no such file or directory, open '.../dist/apps/client/ca/index.html'`

**Cause:** The API expects built client assets at `dist/apps/client/<locale>/index.html` for every supported locale. In dev the middleware still skips serving HTML, but it tries to load all locale files at startup.

**Options:**

- **Ignore in dev:** The server continues to start and listen; API routes and the client dev server (e.g. `npm run start:client` at 4200) work. You can leave this as-is.
- **Clear the error:** Build the client once so the files exist (takes a few minutes):
  ```bash
  npx nx run client:copy-assets && npx nx run client:build:production
  ```
  Then run `npm run start:server` again.

### 3. Full stack: “variable is not set” / Ghostfolio unhealthy

**Symptom:** `WARN The "POSTGRES_USER" variable is not set. Defaulting to a blank string.` and/or `container ghostfolio is unhealthy`

**Cause:** Docker Compose uses the directory of the first `-f` file as the project directory, so it looks for `.env` in `docker/` instead of the repo root. Variable substitution in the compose file then gets blank values, so Ghostfolio receives an invalid `DATABASE_URL` and fails.

**Fix:** Run from **repo root** and pass the project-root `.env` explicitly:

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env up -d
```

Then check agent health: `curl http://localhost:8000/health`

---

## Definition of Done for TICKET-01

- [ ] Ghostfolio runs locally (server + client accessible at localhost:4200)
- [ ] First admin user created, can navigate the app
- [ ] `/agent` directory scaffolded with all placeholder files
- [ ] `requirements.txt` created with real dependency versions
- [ ] `agent/Dockerfile` builds successfully
- [ ] `docker/docker-compose.agent.yml` created
- [ ] Full 4-service Docker stack boots (from repo root): `docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env up -d`
- [ ] Agent health check responds: `curl http://localhost:8000/health` → `{"status":"ok"}`
- [ ] `.env.example` updated with agent variables
- [ ] `docs/tickets/devlog.md` updated with TICKET-01 entry
- [ ] All new files committed on a feature branch

---

## Estimated Time: 2–3 hours

| Task | Estimate |
|------|----------|
| Local env setup + Ghostfolio running | 45 min |
| Agent directory scaffold | 30 min |
| requirements.txt + Dockerfile | 15 min |
| docker-compose.agent.yml + testing | 30 min |
| .env.example update | 10 min |
| Verify full stack + devlog update | 20 min |

---

## After TICKET-01: What Comes Next

**TICKET-02: GhostfolioClient + Auth Module** — Implement the real HTTP client with Bearer token auth, MockClient for tests, JSON fixtures matching actual API responses, and auth lifecycle tests. This is the foundation all 4 tools depend on.
