# Skill: Railway Deployment Orchestrator

Deploy services to Railway with pre-flight checks and post-deploy verification.

## When to Use

User says: "deploy", "push to railway", "deploy to staging", "ship it"

## Workflow

### Step 1: Pre-Flight Checks

**Verify code is committed and pushed:**

```bash
git status
git log --oneline -3
git diff origin/main..HEAD --stat
```

If there are uncommitted changes, warn the user.

**Verify builds pass locally:**

```bash
npx nx build api
npx nx build client
cd agent && python -c "import main; print('Agent imports OK')" && cd ..
```

### Step 2: Identify What to Deploy

Check what changed since last deploy:

```bash
git diff origin/main..HEAD --name-only
```

- Changes in `agent/` → deploy **agent** service
- Changes in `apps/`, `libs/`, `prisma/` → deploy **ghostfolio** service
- Changes in both → deploy both

### Step 3: Deploy Services

**Deploy Ghostfolio (NestJS + Angular + Prisma):**

```bash
npx @railway/cli up --service ghostfolio --ci --message "deploy: <description>"
```

**Deploy Agent (FastAPI):**

```bash
npx @railway/cli up --service agent --ci --path-as-root --message "deploy: <description>" agent
```

IMPORTANT: The `agent` argument at the end tells Railway to use `agent/` as the build context (where the Dockerfile lives).

### Step 4: Post-Deploy Verification

**Wait 60-90 seconds for services to restart, then verify:**

```bash
# Ghostfolio health
curl -sf https://ghostfolio-production-61c8.up.railway.app/api/v1/health

# Agent health
curl -sf https://agent-production-d1f1.up.railway.app/health

# Agent chat (quick smoke test)
curl -s -X POST https://agent-production-d1f1.up.railway.app/api/agent/eval \
  -H "Content-Type: application/json" -d '{}' --max-time 15 | head -5
```

### Step 5: Report Status

| Service    | URL                                       | Status |
| ---------- | ----------------------------------------- | ------ |
| Ghostfolio | ghostfolio-production-61c8.up.railway.app | ?      |
| Agent      | agent-production-d1f1.up.railway.app      | ?      |
| PostgreSQL | Railway managed (Postgres-eRyc)           | ?      |
| Redis      | Railway managed                           | ?      |

## Railway Environment Variables

**Ghostfolio service:**

- `DATABASE_URL` → `${{Postgres-eRyc.DATABASE_URL}}`
- `REDIS_HOST` → `${{Redis.REDISHOST}}`
- `REDIS_PORT` → `${{Redis.REDISPORT}}`
- `REDIS_PASSWORD` → `${{Redis.REDISPASSWORD}}`
- `AGENT_CHAT_URL` → `https://agent-production-d1f1.up.railway.app/api/agent/chat`

**Agent service:**

- `OPENAI_API_KEY` → secret
- `GHOSTFOLIO_API_URL` → `https://ghostfolio-production-61c8.up.railway.app`
- `GHOSTFOLIO_ACCESS_TOKEN` → set after hosted user bootstrap
- `AGENT_CORS_ORIGINS` → `https://ghostfolio-production-61c8.up.railway.app`

## Troubleshooting

| Issue                    | Cause                         | Fix                                      |
| ------------------------ | ----------------------------- | ---------------------------------------- |
| 401/403 from agent tools | Stale GHOSTFOLIO_ACCESS_TOKEN | Create new user, update token, redeploy  |
| CORS errors in browser   | Missing AGENT_CORS_ORIGINS    | Set to ghostfolio domain, redeploy agent |
| Hobby deploys paused     | Railway billing limit         | Check Railway dashboard billing          |
| Agent 404 on /eval       | Old code deployed             | Redeploy agent service                   |
| Build fails              | Missing deps or syntax error  | Fix locally, push, redeploy              |
