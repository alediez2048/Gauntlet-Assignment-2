# AgentForge — What's Happening & What Can I Do Now?

**Project:** Ghostfolio + AI Agent Integration
**Purpose:** Living document that explains what each completed ticket actually did, in plain English. Updated after every ticket so you always know where you stand.
**Last Updated:** Feb 24, 2026

---

## How to Read This Document

After each ticket is completed, a new section gets added below explaining:
1. **What just happened** — plain-English summary, no jargon
2. **What changed** — what's new in the system
3. **What you can do now** — what you can actually run, see, or interact with
4. **What you still can't do** — so you know what's coming next
5. **Analogy** — a simple mental model for the ticket

---

## The Big Picture

```
TICKET-00  Studied the blueprints                         ✅
TICKET-01  Laid the foundation                            ✅
TICKET-02  Installed the plumbing (pipes to Ghostfolio)   ✅
TICKET-03  Built calculator #1 (portfolio performance)    ✅
TICKET-04  Built calculator #2 (transaction categories)   ← YOU ARE HERE
TICKET-05  Built calculator #3 (tax estimates)
TICKET-06  Built calculator #4 (allocation advice)
TICKET-07  Hired the brain (GPT-4o + LangGraph)         ← agent comes alive
TICKET-08  Opened the front door (HTTP endpoint)         ← first conversation possible
TICKET-09  Built the reception desk (chat UI)            ← users can talk to it
TICKET-10  Grand opening (full stack + demo data)        ← everything works together
```

---

## Progress Tracker

| Ticket | Status | Can You Talk to an Agent? |
|--------|--------|--------------------------|
| 00 — Repo indexing | Done | No |
| 01 — Scaffold | Done | No |
| 02 — HTTP client + auth | Done | No |
| 03 — Portfolio analyzer tool | Done | No |
| 04 — Transaction categorizer | **Next** | No |
| 05 — Tax estimator | Pending (deferrable) | No |
| 06 — Allocation advisor | Pending (deferrable) | No |
| 07 — LangGraph agent brain | Pending | In test code only |
| 08 — SSE endpoint | Pending | **Yes — via curl** |
| 09 — Angular chat widget | Pending | **Yes — in browser** |
| 10 — Docker + seed data + E2E | Pending | **Yes — full demo** |

---

## Completed Tickets

---

### TICKET-00: Repository Indexing & Docs Alignment

**What just happened:**
You (with AI assistance) read through the entire Ghostfolio codebase — every controller, every route, every database model, every Docker config. Then you compared the 5 planning documents (PRD, Build Guidelines, etc.) against what the code actually does and found 18 places where the docs were wrong.

**What changed:**
- 4 documentation files were corrected (wrong API versions, wrong file names, wrong date formats, wrong Node.js version)
- 11 Cursor rules files were created — these are like "cheat sheets" that Cursor reads automatically so it doesn't make the same mistakes the docs had

**What you can do now:**
- Nothing runnable yet — this was a research and preparation ticket
- But every future ticket benefits because the docs are now accurate

**What you still can't do:**
- No code exists yet. No agent, no tools, nothing runs.

**Analogy:** You hired an architect to review the blueprints before construction. They found the blueprints said "use 18-gauge wire" but the building actually needs 22-gauge. Fixed it before anyone started building.

---

### TICKET-01: Environment Setup & Agent Scaffold

**What just happened:**
You created the entire directory structure for the Python agent service — but it's all empty shells. Think of it like framing a house: the rooms are defined, the walls are up, but there's no plumbing, no electrical, no furniture.

**What changed:**
- 27 new files created under `agent/` — all placeholders except:
  - `main.py` — a tiny FastAPI server that responds to `/health` with `{"status": "ok"}`
  - `tools/base.py` — the `ToolResult` class that every tool will return
- `requirements.txt` — lists all Python dependencies (FastAPI, LangGraph, httpx, etc.)
- `Dockerfile` — so the agent can run in Docker
- `docker/docker-compose.agent.yml` — adds the agent as a 4th Docker service

**What you can do now:**
```bash
# Build the agent Docker image
docker build -f agent/Dockerfile -t gf-agent:test agent/

# Run it and check health
docker run -p 8000:8000 gf-agent:test
curl http://localhost:8000/health
# → {"status": "ok"}
```

**What you still can't do:**
- The agent doesn't do anything useful — `/health` is the only endpoint
- No tools, no auth, no connection to Ghostfolio

**Analogy:** You framed the house. The rooms exist on paper and in the structure, but turn on a faucet and nothing comes out.

---

### TICKET-02: GhostfolioClient + Auth Module

**What just happened:**
You built the "plumbing" — the HTTP client that connects the agent service to Ghostfolio's API. This includes:
1. **Auth module** (`auth.py`) — knows how to exchange a security token for a Bearer JWT, caches it, and refreshes when it expires
2. **GhostfolioClient** (`ghostfolio_client.py`) — an async HTTP client with 4 methods that call Ghostfolio endpoints, automatically attaching the Bearer token to every request
3. **MockGhostfolioClient** (`mock_client.py`) — a fake version that returns pre-baked JSON from fixture files, so tests never need a real Ghostfolio instance
4. **Fixtures** — sample JSON files that look exactly like real Ghostfolio API responses

**What changed:**
- `agent/auth.py` — token exchange, TTL cache, refresh logic
- `agent/clients/ghostfolio_client.py` — 4 API methods
- `agent/clients/mock_client.py` — same interface, returns fixture data
- 4 fixture JSON files in `agent/tests/fixtures/`
- 9 unit tests passing

**What you can do now:**
```bash
# Run the unit tests
cd agent && python -m pytest tests/unit/ -xvs
# → 9 passed (runs in ~0.07 seconds, no network needed)
```

**What you still can't do:**
- No tools exist yet — the client can fetch data, but nothing processes it
- No agent brain — nobody decides *what* to fetch
- No way to interact — no chat endpoint, no UI

**Analogy:** The plumbing is installed. Water can flow from Ghostfolio into the house. But there are no sinks, no showers, no appliances connected to the pipes yet. You also built a "test faucet" (MockClient) that dispenses bottled water for testing without connecting to the real supply.

---

### TICKET-03: Portfolio Performance Analyzer

**What just happened:**
You built the first real tool — a Python function that analyzes portfolio performance. Here's what it does in plain English:

1. You give it a time period (like "ytd" for year-to-date, or "1y" for one year)
2. It checks if that time period is valid (rejects nonsense like "banana")
3. It calls the GhostfolioClient to fetch performance data from the API
4. It wraps the result in a `ToolResult.ok(data)` on success, or `ToolResult.fail(error)` on failure
5. It **never crashes** — every possible error (bad input, network timeout, auth failure, unexpected exception) gets caught and returned as a structured error

This is a **pure function** — it takes an API client in, returns data out. No LLM, no AI, no magic. Just: validate, fetch, return.

**What changed:**
- `agent/tools/portfolio_analyzer.py` — the actual tool function (43 lines of code)
- `agent/tests/unit/test_portfolio_analyzer.py` — 6 new tests
- Total tests now: **15 passing** (9 from TICKET-02 + 6 new)

**What the tool code actually looks like:**
```python
async def analyze_portfolio_performance(api_client, time_period="max"):
    # Step 1: Reject invalid time periods before making any API call
    if time_period not in VALID_DATE_RANGES:
        return ToolResult.fail("INVALID_TIME_PERIOD")

    # Step 2: Call Ghostfolio through the injected client
    try:
        data = await api_client.get_portfolio_performance(time_period)
        return ToolResult.ok(data)  # Success!
    except GhostfolioClientError as error:
        return ToolResult.fail(error.error_code)  # Known error
    except Exception:
        return ToolResult.fail("API_ERROR")  # Unknown error — still no crash
```

**What you can do now:**
```bash
# Run all 15 tests
cd agent && python -m pytest tests/unit/ -xvs
# → 15 passed in ~0.09 seconds
```

**What you still can't do:**
- This tool only runs inside test code — there's no way to call it from outside
- No agent brain to decide *when* to use this tool
- No chat endpoint, no UI
- Only 1 of 4 tools exists

**Analogy:** You installed the first appliance — a dishwasher. It's connected to the plumbing, it works, you tested it with bottled water (mock data). But nobody lives in the house yet to decide when to run the dishwasher (that's the agent brain in TICKET-07).

---

## Where You Are Right Now

After 4 tickets (00–03), here's what exists:

```
┌─────────────────────────────────────────────────────────┐
│                    WHAT EXISTS NOW                        │
│                                                          │
│   FastAPI Server (:8000)                                 │
│   └── GET /health → {"status": "ok"}                    │
│       (that's the only endpoint)                         │
│                                                          │
│   GhostfolioClient (plumbing)                            │
│   └── Can talk to Ghostfolio API with Bearer auth        │
│   └── Handles token refresh, timeouts, errors            │
│                                                          │
│   Tool #1: Portfolio Analyzer ✅                         │
│   └── Validates input → fetches data → returns result    │
│                                                          │
│   Tool #2: Transaction Categorizer ❌ (TICKET-04 next)   │
│   Tool #3: Tax Estimator ❌                              │
│   Tool #4: Allocation Advisor ❌                         │
│                                                          │
│   Agent Brain (LangGraph + GPT-4o) ❌                    │
│   SSE Endpoint (POST /api/agent/chat) ❌                 │
│   Angular Chat Widget ❌                                 │
│                                                          │
│   Tests: 15 passing, 0 failing                           │
└─────────────────────────────────────────────────────────┘
```

**In human terms:** You have a house with framing (TICKET-01), plumbing (TICKET-02), and one working appliance (TICKET-03). The next step is to install the second appliance (transaction categorizer).

---

## What's Coming Next

### TICKET-04: Transaction Categorizer (Next Up)

**What will happen:**
The second tool gets built. Same pattern as TICKET-03 but for a different job:
1. Takes the GhostfolioClient and a `days_back` parameter (like 90 days)
2. Fetches all your transactions/activities from Ghostfolio
3. Groups them by type: BUY, SELL, DIVIDEND, FEE, INTEREST, LIABILITY
4. Computes summary stats: total invested, total dividends, total fees, most traded symbol
5. Returns `ToolResult.ok(categorized_data)`

**After this ticket:**
- 2 of 4 tools will work
- Test count will be ~21+
- Still no agent, no chat, no UI — just another tested calculator

**Analogy:** Installing the washing machine. Same plumbing, different appliance, different job.

---

## Key Concepts

### Why Are Tools Separate From the Agent?

Think of it like a calculator app on your phone:
- The **tools** are the math operations (add, subtract, multiply, divide)
- The **agent** (TICKET-07) is the part that reads your question ("What's 15% of 230?"), figures out which operation to use (multiply), runs it, and tells you the answer in English

You build the math operations first (TICKET-03–06), then the brain that uses them (TICKET-07).

### Why Mock Everything?

Every tool is tested with fake data (`MockGhostfolioClient`) instead of a real Ghostfolio instance. This means:
- Tests run in milliseconds (no network calls)
- Tests are deterministic (same fake data every time)
- You don't need Docker running to develop
- Real Ghostfolio data isn't needed until TICKET-10 (the full demo)

### When Do I Need Real Data in Ghostfolio?

| When | What | Required? |
|------|------|-----------|
| TICKET-03–06 | Optional: validate tools against live Ghostfolio | No |
| TICKET-07–08 | Integration tests use mocks | No |
| **TICKET-10** | **Create seed-data.json, import into Ghostfolio, run E2E** | **Yes** |

---

## Seed Data Import (For When You Reach TICKET-10)

```bash
# 1. Boot Ghostfolio
docker compose -f docker/docker-compose.yml up -d

# 2. Open browser → http://localhost:3333
#    Click "Get Started" → creates anonymous user with security token

# 3. Copy security token → put in .env as GHOSTFOLIO_ACCESS_TOKEN

# 4. Get Bearer token
TOKEN=$(curl -s -X POST http://localhost:3333/api/v1/auth/anonymous \
  -H "Content-Type: application/json" \
  -d '{"accessToken":"<your-security-token>"}' | jq -r '.authToken')

# 5. Import seed data
curl -X POST http://localhost:3333/api/v1/import \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @docker/seed-data.json
```

---

## TICKET-10.1 Hosted Railway Run (Current)

Use this for the hosted demo path validated in TICKET-10.1.

### Hosted Endpoints (staging)

- Ghostfolio UI/API: `https://ghostfolio-production-61c8.up.railway.app`
- Agent API: `https://agent-production-d1f1.up.railway.app`
- Agent chat endpoint for runtime injection: `https://agent-production-d1f1.up.railway.app/api/agent/chat`

### Required Order (Do Not Skip)

1. **Local gate first**
   - Run clean local rebuild and health checks before touching hosted rollout.
2. **Railway health checks**
   - `GET https://ghostfolio-production-61c8.up.railway.app/api/v1/health`
   - `GET https://agent-production-d1f1.up.railway.app/health`
3. **Hosted auth + import bootstrap**
   - Create user (`POST /api/v1/user`), exchange token (`POST /api/v1/auth/anonymous`), then import activities.
   - Note: hosted import may reject some `YAHOO` symbols; use the Railway runbook transform path in
     `Docs/reference/railway.md` when needed.
4. **Hosted chat regression**
   - Run all 7 checks: performance, transactions, tax, allocation, follow-up continuity, clarifier, invalid input.
   - Verify SSE contract (`thinking` first, terminal `done`/`error`, no hangs).

### Runtime Configuration

- Agent CORS is now env-driven via `AGENT_CORS_ORIGINS` (keeps localhost defaults + hosted origins).
- Ghostfolio injects runtime chat URL via `AGENT_CHAT_URL` into `window.__GF_AGENT_CHAT_URL__`.
- Frontend reads runtime endpoint from `window.__GF_AGENT_CHAT_URL__` and falls back to localhost only when unset.

### Full Railway Runbook

- See `Docs/reference/railway.md` for step-by-step provisioning, deployment, smoke tests, troubleshooting, and rollback.
