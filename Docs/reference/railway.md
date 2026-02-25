# Railway Deployment Runbook (TICKET-10.1)

This runbook captures the deployment path validated in TICKET-10.1.

## Project and Services

- Railway project: `gauntlet-ticket-10-1-staging`
- Services:
  - `ghostfolio`
  - `agent`
  - `Postgres-eRyc`
  - `Redis`

## Hosted Domains

- Ghostfolio: `https://ghostfolio-production-61c8.up.railway.app`
- Agent: `https://agent-production-d1f1.up.railway.app`
- Agent chat endpoint: `https://agent-production-d1f1.up.railway.app/api/agent/chat`

## One-Time Provisioning

```bash
# Create project
npx @railway/cli init -n gauntlet-ticket-10-1-staging --json

# Add managed databases
printf '\n' | npx @railway/cli add --database postgres --json
printf '\n' | npx @railway/cli add --database redis --json

# Add empty app services
printf '\n' | npx @railway/cli add --service ghostfolio --json
printf '\n' | npx @railway/cli add --service agent --json
```

## Environment Variables

Set variables with Railway CLI; keep secrets in Railway, never in git.

### Ghostfolio service

- `ACCESS_TOKEN_SALT` = random 32+ byte hex
- `JWT_SECRET_KEY` = random 32+ byte hex
- `DATABASE_URL=${{Postgres-eRyc.DATABASE_URL}}`
- `REDIS_HOST=${{Redis.REDISHOST}}`
- `REDIS_PORT=${{Redis.REDISPORT}}`
- `REDIS_PASSWORD=${{Redis.REDISPASSWORD}}`
- `ROOT_URL=https://ghostfolio-production-61c8.up.railway.app`
- `AGENT_CHAT_URL=https://agent-production-d1f1.up.railway.app/api/agent/chat`

### Agent service

- `OPENAI_API_KEY` (secret)
- `GHOSTFOLIO_API_URL=https://ghostfolio-production-61c8.up.railway.app`
- `GHOSTFOLIO_ACCESS_TOKEN` (set after hosted user bootstrap)
- `AGENT_CORS_ORIGINS=https://ghostfolio-production-61c8.up.railway.app`

## Deploy Commands

```bash
# Deploy Ghostfolio (repo root Dockerfile)
npx @railway/cli up --service ghostfolio --ci --message "TICKET-10.1 ghostfolio deploy"

# Deploy agent (agent/Dockerfile)
npx @railway/cli up --service agent --ci --path-as-root --message "TICKET-10.1 agent deploy" agent
```

## Hosted Bootstrap + Import

Use this sequence after deploy:

1. Create hosted user (`POST /api/v1/user`) and capture `accessToken`.
2. Set `GHOSTFOLIO_ACCESS_TOKEN` on Railway `agent` service.
3. Exchange Bearer token (`POST /api/v1/auth/anonymous`).
4. Import seed activities.

Note: hosted import can reject some `YAHOO` symbols depending on data-source validation behavior.
For hosted reliability in TICKET-10.1, a temporary import transform was used:

- Keep 26 activity rows from `docker/seed-data.json`.
- Convert rows with `dataSource=YAHOO` to `dataSource=MANUAL`.
- Replace each market symbol with a deterministic UUID per original symbol.

This preserved scenario coverage while avoiding hosted symbol validation failures.

## Smoke Checks

```bash
# Health
curl -sS -o /dev/null -w "%{http_code}\n" \
  https://ghostfolio-production-61c8.up.railway.app/api/v1/health
curl -sS -o /dev/null -w "%{http_code}\n" \
  https://agent-production-d1f1.up.railway.app/health
```

Then run hosted chat regression against `POST /api/agent/chat`:

- `How is my portfolio doing ytd?` -> `analyze_portfolio_performance`
- `Categorize my transactions for max range.` -> `categorize_transactions`
- `Estimate my tax liability for 2025 in middle bracket.` -> `estimate_capital_gains_tax`
- `Am I diversified enough for a balanced profile?` -> `advise_asset_allocation`
- Follow-up continuity in same `thread_id`
- Clarifier behavior on out-of-domain query
- Invalid input error path (`tax year 2019`) -> `INVALID_TAX_YEAR`

SSE contract must hold for each scenario:

- First event: `thinking`
- Terminal event: `done` or `error`
- No stream hang

## Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `401` or `403` from hosted tool calls | stale/invalid `GHOSTFOLIO_ACCESS_TOKEN` in agent | create new hosted user token, update agent variable, wait for redeploy |
| Import fails on `symbol ... not valid for data source YAHOO` | hosted symbol validation mismatch | use MANUAL transform import path for hosted seed bootstrap |
| Browser chat cannot reach agent | wrong runtime endpoint injection | verify `AGENT_CHAT_URL` on ghostfolio and `window.__GF_AGENT_CHAT_URL__` runtime value |
| Browser CORS error on chat POST | agent origin missing | set `AGENT_CORS_ORIGINS` to hosted ghostfolio domain and redeploy agent |
| Ghostfolio startup fails with DB/Redis errors | broken service variable references | verify `${{Postgres-eRyc.*}}` and `${{Redis.*}}` references |

## Rollback

Fastest safe rollback path:

1. Revert recent service variable changes (especially `GHOSTFOLIO_ACCESS_TOKEN`, CORS, URL vars).
2. Redeploy last known-good revision for affected service:
   - `npx @railway/cli service redeploy --service ghostfolio`
   - `npx @railway/cli service redeploy --service agent`
3. Re-run smoke sequence (health -> auth/import -> 2-3 chat probes).
