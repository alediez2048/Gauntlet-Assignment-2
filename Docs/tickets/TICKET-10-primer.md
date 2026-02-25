# TICKET-10 Primer: Docker Compose + Seed Data + E2E Validation

**For:** New Cursor Agent session  
**Project:** AgentForge - Ghostfolio + AI Agent Integration  
**Date:** Feb 25, 2026  
**Previous work:** TICKET-09 completed (Angular chat UI + SSE rendering + HTTPS localhost CORS fix), commit `206cdf138` on `main`

---

## What Is This Ticket?

TICKET-10 is the full integration milestone:

- Boot the complete 4-service stack reproducibly with Docker Compose.
- Seed realistic portfolio activity data into Ghostfolio.
- Validate end-to-end behavior with demo-grade queries through the real UI and agent.

This is where "all parts work together" with real runtime data.

### Why It Matters

- **Demo readiness:** The app must run as a reproducible full stack, not only in hybrid dev.
- **Data realism:** Tool behavior needs seeded holdings/orders to produce meaningful outputs.
- **Confidence before edge cases:** TICKET-11 hardening only makes sense after the golden path is stable.
- **Operational proof:** Confirms auth, networking, and SSE behavior across service boundaries.

---

## Branching Rule (Mandatory)

Every ticket must use a dedicated feature branch.

- **Branch for this ticket:** `feature/TICKET-10-docker-seed-e2e`
- **Do not implement TICKET-10 directly on `main`.**
- **Do not continue TICKET-10 work on prior ticket branches.**

---

## Commit Workflow (Mandatory)

Workspace hooks can fail for unrelated Nx/plugin reasons.  
For this ticket, keep the established workflow:

1. Run verification commands manually first.
2. Stage only TICKET-10 files explicitly (never `git add .`).
3. Commit with `--no-verify`.

Example:

```bash
git add "docker/seed-data.json" \
        "agent/tests/e2e/golden_path.ipynb" \
        "Docs/tickets/devlog.md"
git commit --no-verify -m "TICKET-10: add seed data and full-stack E2E validation workflow"
```

---

## Runtime Modes (Critical Context)

| Mode | Ghostfolio UI | Ghostfolio API | Agent API | Use Case |
| --- | --- | --- | --- | --- |
| **Full Docker Stack (primary for TICKET-10)** | `http://localhost:3333/en` | `http://localhost:3333` | `http://localhost:8000` | Compose + seed + end-to-end validation |
| Hybrid Dev (secondary fallback) | `https://localhost:4200/en/home` | `http://localhost:3333` | `http://localhost:8000` | Frontend-only iteration |

Important notes:

- For this ticket, use the **full Docker mode as source of truth**.
- Run from repo root and pass env explicitly to avoid compose variable resolution issues:
  - `docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env ...`
- Do not run hybrid and full-stack flows simultaneously unless intentionally debugging.

---

## What Is Already Done (Carry-Forward Context)

- Agent UI is integrated into Ghostfolio and streams typed SSE events end-to-end.
- Agent endpoint exists: `POST /api/agent/chat` with event contract:
  - `thinking`, `tool_call`, `tool_result`, `token`, `done`, `error`
- Agent overlay compose file exists: `docker/docker-compose.agent.yml`
- Dev agent overlay exists: `docker/docker-compose.agent-dev.yml`
- FastAPI CORS already includes localhost HTTP/HTTPS variants for local development.

---

## What TICKET-10 Must Accomplish

### Goal

Establish a reproducible demo runtime with seeded portfolio data and validated full-stack behavior.

### Deliverables Checklist

### A. Docker Compose Full-Stack Verification

- [ ] Verify full 4-service startup works from clean state:
  - `postgres`, `redis`, `ghostfolio`, `agent`
- [ ] Confirm health checks:
  - `GET http://localhost:3333/api/v1/health`
  - `GET http://localhost:8000/health`
- [ ] Confirm `agent` can authenticate and call Ghostfolio APIs in full-stack mode.

### B. Seed Data Package

- [ ] Create `docker/seed-data.json` with valid Ghostfolio import payload shape:
  - top-level `{ "activities": [...] }`
- [ ] Use required fields for activity imports:
  - `currency`, `date` (ISO-8601), `fee`, `quantity`, `symbol`, `type`, `unitPrice`
  - `dataSource` where required (`YAHOO` or `COINGECKO`; optional for `FEE`/`INTEREST`/`LIABILITY`)
- [ ] Include realistic multi-month data that exercises all major tool paths.

### C. Seed Import Workflow

- [ ] Document + verify import via Ghostfolio API (not raw DB writes):
  - auth exchange via `POST /api/v1/auth/anonymous`
  - import via `POST /api/v1/import`
- [ ] Ensure import is repeatable after clean reset.

### D. End-to-End Validation (5 Query Golden Path)

- [ ] Add E2E notebook at `agent/tests/e2e/golden_path.ipynb`.
- [ ] Include 5 scripted queries covering:
  1. Portfolio performance
  2. Transaction categorization
  3. Tax estimate
  4. Allocation analysis
  5. Follow-up query demonstrating thread continuity
- [ ] Record outputs/snapshots and confirm no runtime regressions.

### E. Ticket Documentation

- [ ] Update `Docs/tickets/devlog.md` with:
  - completed scope
  - commands executed
  - files changed
  - issues and resolutions
  - updated running totals

---

## Seed Data Requirements (So All Tools Return Meaningful Results)

Design `docker/seed-data.json` so each core capability has coverage:

| Capability | Seed Data Requirement |
| --- | --- |
| Portfolio performance | Multiple buys over time; non-zero current valuation |
| Transactions | Mix of `BUY`, `SELL`, `DIVIDEND`, `FEE`, `INTEREST` (and optional `LIABILITY`) |
| Tax estimation | At least one realized gain and one realized loss year |
| Allocation analysis | Multiple symbols/assets, concentration imbalance visible |

Additional guidance:

- Span at least ~12 months of activity for richer period queries.
- Use symbols/data sources that Ghostfolio can resolve (`YAHOO`, `COINGECKO`).
- Keep values sane and internally consistent (no negative quantities/prices).

---

## Suggested 5 E2E Queries

Use these in both UI/manual and notebook checks:

1. `How is my portfolio doing ytd?`
2. `Categorize my transactions for max range.`
3. `Estimate my capital gains tax for 2025 in middle bracket.`
4. `Am I diversified enough for a balanced profile?`
5. `Based on that, where am I most concentrated?` (follow-up in same thread)

Expected quality bar:

- Correct tool route per query
- No stream hangs/crashes
- Safe, concise user-facing responses
- Follow-up preserves thread context (`thread_id` continuity)

---

## Manual Runbook (Full Docker Mode)

1. Ensure `.env` is populated (including `OPENAI_API_KEY` and `GHOSTFOLIO_ACCESS_TOKEN`).
2. Clean start:
   - `docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env down -v`
   - `docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env up -d --build`
3. Check health:
   - `curl http://localhost:3333/api/v1/health`
   - `curl http://localhost:8000/health`
4. Import seed data:
   - exchange access token -> bearer token
   - `POST /api/v1/import` with `docker/seed-data.json`
5. Open `http://localhost:3333/en` and run the 5 queries via chat panel.
6. Run notebook scenarios in `agent/tests/e2e/golden_path.ipynb`.
7. Capture evidence in devlog before commit.

---

## Files to Modify

| File | Action |
| --- | --- |
| `docker/seed-data.json` | New import payload for demo portfolio |
| `agent/tests/e2e/golden_path.ipynb` | New 5-scenario E2E notebook |
| `Docs/tickets/devlog.md` | Add TICKET-10 completion entry |
| `docker/docker-compose.agent.yml` | Only if small adjustments are needed for reproducible boot |
| Optional: `scripts/*` or `docker/*` helper docs | Only if needed to keep seed/import repeatable |

## Files You Should NOT Modify (Unless Blocked)

- `apps/client/**` UI implementation (already done in TICKET-09)
- `agent/graph/**` orchestration logic (unless a true E2E blocker appears)
- Broad Ghostfolio source refactors unrelated to compose/seed/E2E
- Secrets files (`.env`) in git history

---

## Definition of Done for TICKET-10

- [ ] Full 4-service Docker stack boots cleanly from repo root command.
- [ ] Seed import succeeds through Ghostfolio API with valid payload.
- [ ] Portfolio data is visible/usable for agent responses.
- [ ] 5 golden-path queries run successfully end-to-end.
- [ ] Thread continuity verified on follow-up prompt.
- [ ] `agent/tests/e2e/golden_path.ipynb` exists and is runnable.
- [ ] `Docs/tickets/devlog.md` updated with accurate closeout details.
- [ ] Work committed on `feature/TICKET-10-docker-seed-e2e` with `--no-verify`.

---

## Estimated Time: 180-300 minutes

| Task | Estimate |
| --- | --- |
| Seed payload creation + validation | 45 min |
| Compose clean-boot verification + fixes | 45 min |
| Seed import workflow scripting/checks | 30 min |
| 5-query UI + notebook E2E validation | 60 min |
| Devlog closeout + commit workflow | 20 min |

---

## After TICKET-10: What Comes Next

- **TICKET-11: Edge Case Hardening + Golden Path E2E**  
  Expand adversarial/robustness coverage (empty portfolio, nonsense/prompt injection, ambiguity, rapid-fire behavior) and tighten demo reliability.

