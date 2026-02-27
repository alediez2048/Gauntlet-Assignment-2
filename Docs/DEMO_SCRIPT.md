# AgentForge Demo Script

A 5-query scripted walkthrough demonstrating single-tool analysis, multi-step orchestration, edge case handling, and conversation memory.

## Pre-Demo Checklist

- [ ] All 4 containers healthy: `docker ps --format "table {{.Names}}\t{{.Status}}"`
- [ ] Ghostfolio UI loads at http://localhost:3333 (or production URL)
- [ ] Signed in with the seed user's access token
- [ ] Agent health check: `curl http://localhost:8000/health`
- [ ] Chat FAB visible (bottom-right corner of the Ghostfolio UI)
- [ ] Portfolio shows holdings (SPY, AAPL, MSFT, NVDA, BND, VNQ, TSLA)

---

## Demo Flow

### Query 1: Single Tool — Portfolio Performance

**Type this:**

> How is my portfolio doing year to date?

**What happens:**

1. `thinking` event — agent analyzes the request
2. `tool_call` — selects `analyze_portfolio_performance` with `time_period=ytd`
3. `tool_result` — tool fetches data from Ghostfolio and returns success
4. Synthesized response streams in with YTD return percentage and top/bottom holdings

**Point out to the grader:**

- SSE streaming — response appears incrementally, not all at once
- Citations — numbered source references [1], [2] linking claims to data points
- Confidence badge — color-coded (green/yellow/red) based on data quality
- Token usage — cost tracking in the `done` event

---

### Query 2: Single Tool — Transaction Categorization

**Type this:**

> Categorize my recent transactions

**What happens:**

1. Routes to `categorize_transactions` with `date_range=max`
2. Returns breakdown by type: BUY, SELL, DIVIDEND, FEE, INTEREST, LIABILITY
3. Shows all 26 seed transactions across 7 symbols

**Point out to the grader:**

- Different tool selected automatically based on intent
- Structured data presentation with category counts

---

### Query 3: Multi-Tool — Comprehensive Review

**Type this:**

> Give me a full financial health checkup

**What happens:**

1. Router detects a multi-step query
2. Orchestrator chains 2-3 tools sequentially (portfolio + allocation + compliance)
3. Multiple `tool_call` / `tool_result` pairs stream in
4. Synthesizer combines all results using the multi-step synthesis prompt
5. Response includes cross-cutting insights

**Point out to the grader:**

- Multi-step orchestration — the orchestrator's `next_step` edge loops back to the router
- Each tool executes independently with its own validation
- Final synthesis draws connections across tool outputs (e.g., concentration risk from allocation correlating with compliance flags)
- This is the core "non-trivial agent" capability

---

### Query 4: Edge Case — Out of Domain

**Type this:**

> What's the weather in New York?

**What happens:**

1. Router classifies as `clarify` (out of scope)
2. No tool is called
3. Agent responds with a polite refusal and lists supported capabilities

**Point out to the grader:**

- Safety guardrails — the agent doesn't hallucinate or force-fit a financial tool
- Helpful redirection — lists what the agent can actually do
- No unnecessary API calls or LLM tool invocations

---

### Query 5: Thread Continuity — Follow-Up

**Type this (in the same chat thread):**

> Now check for any wash sale violations

**What happens:**

1. Routes to `check_compliance` with `check_type=wash_sale`
2. Uses the same `thread_id` as previous queries (conversation memory)
3. Response may reference context from earlier in the conversation

**Point out to the grader:**

- Thread persistence — the agent maintains conversation history via LangGraph's checkpointer
- Context-aware routing — "now" implies continuation of the ongoing analysis
- Different tool from Query 3's compliance check (wash_sale vs all)

---

## Narration Tips

As each query executes, narrate the agent's reasoning in real time:

> "Notice the agent identified this as a portfolio analysis request, so it's calling the portfolio performance tool. The tool fetched holdings from Ghostfolio's API. Now it's analyzing the data and here comes the synthesis with a structured breakdown and source citations."

For the multi-step query:

> "This is where multi-step orchestration kicks in. The orchestrator detected that a full health check requires multiple tools. Watch as it chains portfolio analysis, then allocation advice, then compliance — each with its own tool call and validation step. The final synthesis pulls insights from all three."

---

## CLI Backup

If the UI is unavailable, demonstrate via curl. First get an auth token:

```bash
AUTH_TOKEN=$(curl -sS -X POST http://localhost:3333/api/v1/auth/anonymous \
  -H "Content-Type: application/json" \
  -d '{"accessToken":"<YOUR_ACCESS_TOKEN>"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['authToken'])")
```

Then run the 5 queries:

```bash
# Query 1: Portfolio performance
curl -N -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{"message":"How is my portfolio doing year to date?","thread_id":"demo-1"}'

# Query 2: Transactions
curl -N -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{"message":"Categorize my recent transactions","thread_id":"demo-1"}'

# Query 3: Multi-tool health check
curl -N -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{"message":"Give me a full financial health checkup","thread_id":"demo-1"}'

# Query 4: Edge case
curl -N -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{"message":"What is the weather in New York?","thread_id":"demo-1"}'

# Query 5: Thread continuity
curl -N -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{"message":"Now check for any wash sale violations","thread_id":"demo-1"}'
```

---

## Recovery Procedures

| Problem              | Fix                                                                                                               |
| -------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Agent not responding | `docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env restart gf-agent` |
| Auth error (401)     | Re-run the seed script from the README, update `GHOSTFOLIO_ACCESS_TOKEN` in `.env`                                |
| Slow first response  | Normal — first query warms the LLM connection. Subsequent queries are faster.                                     |
| Rate limit (429)     | Wait 60 seconds, or check your [OpenAI usage dashboard](https://platform.openai.com/usage)                        |
| Ghostfolio unhealthy | `docker compose ... restart ghostfolio` and wait for health check to pass                                         |
