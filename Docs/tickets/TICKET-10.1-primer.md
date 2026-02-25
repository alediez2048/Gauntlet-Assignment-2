# TICKET-10.1 Primer: Full E2E Regression + Railway Deployment

**For:** New Cursor Agent session  
**Project:** AgentForge - Ghostfolio + AI Agent Integration  
**Date:** Feb 25, 2026  
**Previous work:** TICKET-10 completed (full Docker stack + seed import + golden-path notebook), commit `42a21e202` on `feature/TICKET-10-docker-seed-e2e`

---

## What Is This Ticket?

TICKET-10.1 is the release-readiness ticket between local demo success and public cloud delivery:

- Test everything built so far end-to-end (not just one happy path).
- Deploy the full solution to Railway as a staging/production-like environment.
- Verify the hosted stack behaves like local Docker, including SSE chat behavior and tool routing.

This ticket turns "works on localhost" into "works on hosted infrastructure."

### Why It Matters

- **Deployment proof:** The project must run outside local Docker to be demo/interview ready.
- **Integration confidence:** Confirms service-to-service auth/network behavior in real hosted topology.
- **Regression protection:** Re-validates all major capabilities before edge-case hardening.
- **Operational readiness:** Produces an explicit runbook for deploy, verify, and recover.

---

## Branching Rule (Mandatory)

Every ticket must use a dedicated feature branch.

- **Branch for this ticket:** `feature/TICKET-10-1-e2e-railway-deploy`
- **Do not implement TICKET-10.1 directly on `main`.**
- **Do not continue TICKET-10.1 work on prior ticket branches.**

---

## Commit Workflow (Mandatory)

Workspace hooks can fail for unrelated Nx/plugin reasons.  
For this ticket, keep the established workflow:

1. Run verification commands manually first.
2. Stage only TICKET-10.1 files explicitly (never `git add .`).
3. Commit with `--no-verify`.

Example:

```bash
git add "agent/main.py" \
        "agent/tests/e2e/golden_path.ipynb" \
        "Docs/reference/demo.md" \
        "Docs/tickets/devlog.md"
git commit --no-verify -m "TICKET-10.1: validate full E2E matrix and deploy to Railway"
```

---

## Runtime Targets (Critical Context)

| Environment | Ghostfolio UI | Ghostfolio API | Agent API | Primary Use |
| --- | --- | --- | --- | --- |
| **Local Docker baseline** | `http://localhost:3333/en` | `http://localhost:3333` | `http://localhost:8000` | Regression baseline before cloud deploy |
| **Railway staging (new in this ticket)** | `https://<ghostfolio-staging-domain>/en` | `https://<ghostfolio-staging-domain>` | `https://<agent-staging-domain>` | Hosted E2E + deployment validation |

Important notes:

- Local Docker remains the first gate (must pass before Railway).
- Railway is the source of truth for hosted validation in this ticket.
- Keep local and Railway data clearly separated (avoid token/domain confusion).

---

## What Is Already Done (Carry-Forward Context)

- Full 4-service local stack boots reproducibly with Docker Compose.
- Seed import path works via Ghostfolio API (`auth/anonymous` -> `import`).
- E2E notebook exists at `agent/tests/e2e/golden_path.ipynb`.
- Agent SSE endpoint streams `thinking`, `tool_call`, `tool_result`, `token`, `done`, `error`.
- Follow-up thread continuity has been fixed for same-thread prompts.
- Allocation normalization and routing follow-up fixes are already in place.

---

## What TICKET-10.1 Must Accomplish

### Goal

Prove that all built capabilities are stable end-to-end and deployable on Railway with a repeatable runbook.

### Deliverables Checklist

### A. Comprehensive End-to-End Regression Matrix (Local Baseline)

- [ ] Re-run clean local stack (`down -v` + `up -d --build`).
- [ ] Validate health endpoints:
  - `GET /api/v1/health` (Ghostfolio)
  - `GET /health` (agent)
- [ ] Re-validate seed/import workflow and data visibility.
- [ ] Execute regression scenarios covering:
  1. Portfolio performance
  2. Transaction categorization
  3. Tax estimation
  4. Allocation analysis
  5. Follow-up continuity
  6. Clarifier/out-of-domain behavior
  7. Graceful error behavior for invalid inputs
- [ ] Confirm no stream hangs and clean terminal events for each scenario.

### B. Railway Deployment Architecture + Config

- [ ] Define Railway service topology:
  - `ghostfolio` service
  - `agent` service
  - `postgres` service
  - `redis` service
- [ ] Configure environment variables for each service (no secrets in git).
- [ ] Ensure agent-to-ghostfolio URL wiring works in Railway private/public networking.
- [ ] Ensure CORS/origin policy includes Railway Ghostfolio domain for agent chat POST.
- [ ] Ensure frontend agent chat endpoint points to Railway agent URL (runtime-safe config).

### C. Railway Deploy + Smoke Tests

- [ ] Deploy Ghostfolio and dependencies to Railway.
- [ ] Deploy agent service to Railway.
- [ ] Verify hosted health checks pass.
- [ ] Verify auth exchange and import path in Railway environment.
- [ ] Run all major chat scenarios through hosted UI and/or scripted API checks.
- [ ] Capture evidence (responses, logs, screenshots) for closeout.

### D. Release Runbook + Rollback Notes

- [ ] Document step-by-step deployment runbook for Railway.
- [ ] Document common failure modes and recovery steps:
  - bad access token
  - CORS mismatch
  - wrong agent endpoint URL
  - DB/Redis connection issues
- [ ] Define rollback path (previous Railway deployment or env revert).

### E. Ticket Documentation

- [ ] Update `Docs/reference/demo.md` with hosted run flow.
- [ ] Update `Docs/tickets/devlog.md` with:
  - completed scope
  - commands executed
  - files changed
  - issues and resolutions
  - updated running totals

---

## End-to-End Test Matrix (Must Be Covered)

| Category | Scenario | Expected Result |
| --- | --- | --- |
| Health | Ghostfolio + agent health endpoints | Both return 200 |
| Auth | `POST /api/v1/auth/anonymous` with valid access token | Returns Bearer token |
| Data import | `POST /api/v1/import` with `docker/seed-data.json` | Returns success (201) |
| Tool route: performance | `How is my portfolio doing ytd?` | `analyze_portfolio_performance` route |
| Tool route: transactions | `Categorize my transactions for max range.` | `categorize_transactions` route |
| Tool route: tax | `Estimate my tax liability for 2025 in middle bracket.` | `estimate_capital_gains_tax` route |
| Tool route: allocation | `Am I diversified enough for a balanced profile?` | `advise_asset_allocation` route |
| Follow-up continuity | `Based on that, where am I most concentrated?` in same thread | same thread_id + coherent follow-up |
| Clarifier behavior | out-of-domain prompt (e.g. weather) | safe clarification response |
| SSE contract | stream ordering and terminal event | starts with `thinking`, ends with `done` or `error` |

---

## Railway Deployment Runbook (Suggested)

1. **Prepare local baseline first**
   - Ensure all local E2E checks are green.
2. **Create/prepare Railway project**
   - Provision PostgreSQL + Redis services.
3. **Deploy Ghostfolio service**
   - Use existing Ghostfolio deployment method (container/image).
   - Wire DB and Redis env vars.
4. **Deploy agent service**
   - Build from `agent/Dockerfile`.
   - Set `OPENAI_API_KEY`, `GHOSTFOLIO_API_URL`, `GHOSTFOLIO_ACCESS_TOKEN`.
5. **Configure cross-service URLs**
   - Agent -> Ghostfolio must target Railway Ghostfolio URL.
   - Frontend chat endpoint must target Railway agent `/api/agent/chat`.
6. **Configure CORS/origins**
   - Agent must allow Ghostfolio Railway origin.
7. **Run hosted smoke tests**
   - health -> auth -> import -> 5+ chat scenarios.
8. **Capture evidence and update docs/devlog**

---

## Railway Environment Variable Checklist

Use this as a minimum checklist (exact values differ by Railway project/service):

- **Ghostfolio service**
  - `ACCESS_TOKEN_SALT`
  - `JWT_SECRET_KEY`
  - `DATABASE_URL` (Railway Postgres)
  - `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` (Railway Redis)
  - `ROOT_URL` (public Ghostfolio domain)
- **Agent service**
  - `OPENAI_API_KEY`
  - `GHOSTFOLIO_API_URL` (Ghostfolio Railway URL)
  - `GHOSTFOLIO_ACCESS_TOKEN` (from the Railway Ghostfolio user)
  - `PORT` (if required by Railway runtime)
- **Never commit**
  - live API keys/tokens/passwords

---

## Files to Modify

| File | Action |
| --- | --- |
| `Docs/reference/demo.md` | Add hosted/Railway E2E run instructions |
| `Docs/tickets/devlog.md` | Add TICKET-10.1 closeout entry |
| `agent/tests/e2e/golden_path.ipynb` | Add/extend hosted test cells if needed |
| `agent/main.py` | CORS/runtime config updates for Railway domain(s), if required |
| `apps/api/src/middlewares/html-template.middleware.ts` | Optional runtime chat URL injection if needed |
| Optional: `.env.railway.example` or `Docs/reference/railway.md` | Deployment config documentation |

## Files You Should NOT Modify (Unless Blocked)

- Broad Ghostfolio refactors unrelated to deploy/testing
- Agent tool logic unless a true hosted regression is found
- Secrets files (`.env`, Railway secrets) in git history

---

## Definition of Done for TICKET-10.1

- [ ] Local full-stack E2E regression matrix passes.
- [ ] Railway services are deployed and healthy.
- [ ] Hosted auth + seed import workflow succeeds.
- [ ] Hosted 5-query golden path succeeds end-to-end.
- [ ] Follow-up continuity is verified in hosted environment.
- [ ] Clarifier and error paths are validated as safe/non-crashing.
- [ ] Deployment + verification runbook is documented.
- [ ] `Docs/tickets/devlog.md` is updated with complete closeout details.
- [ ] Work committed on `feature/TICKET-10-1-e2e-railway-deploy` with `--no-verify`.

---

## Estimated Time: 240-420 minutes

| Task | Estimate |
| --- | --- |
| Local full regression pass + evidence capture | 60 min |
| Railway service setup + env wiring | 75 min |
| Railway deployment + smoke tests | 75 min |
| Hosted E2E scenario validation + fixes | 90 min |
| Documentation/devlog closeout | 30 min |

---

## After TICKET-10.1: What Comes Next

- **TICKET-11: Edge Case Hardening + Robustness E2E**  
  Expand adversarial/chaos scenarios (empty portfolio, malformed prompts, rapid-fire turns, partial outages) now that hosted deployment is proven.

