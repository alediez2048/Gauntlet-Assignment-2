# Environment Guide

Quick reference for running, stopping, seeding, and troubleshooting the Ghostfolio + Agent stack.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  LOCAL (Docker Compose)              │  PRODUCTION (Railway)    │
│                                      │                          │
│  gf-postgres (:5432)                 │  Postgres-eRyc (managed) │
│       ↕                              │       ↕                  │
│  gf-redis (:6379)                    │  Redis (managed)         │
│       ↕                              │       ↕                  │
│  ghostfolio (:3333)  ←──────────→    │  ghostfolio (public URL) │
│       ↕                              │       ↕                  │
│  gf-agent (:8000)                    │  agent (public URL)      │
└─────────────────────────────────────────────────────────────────┘
```

**All 4 services must be healthy before the agent can answer questions.**

---

## 1. Local Environment

### 1.1 Start Everything (the one command)

From repo root:

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env up -d --build
```

This starts **4 containers** on the `ghostfolio-development_default` network:

| Container     | Image                        | Port  | Healthcheck  |
|---------------|------------------------------|-------|--------------|
| `gf-postgres` | `postgres:15-alpine`        | 5432  | `pg_isready` |
| `gf-redis`    | `redis:alpine`              | 6379  | `redis-cli ping` |
| `ghostfolio`  | `ghostfolio/ghostfolio:latest` | 3333 | `curl /api/v1/health` |
| `gf-agent`    | built from `agent/Dockerfile` | 8000 | `curl /health` |

### 1.2 Verify Health

```bash
# All containers healthy?
docker ps --format "table {{.Names}}\t{{.Status}}"

# Individual checks
curl -s http://localhost:3333/api/v1/health   # → 200
curl -s http://localhost:8000/health          # → {"status":"ok","version":"..."}
```

### 1.3 Seed Data (first time only)

After a fresh Postgres volume, Ghostfolio starts with no users. Bootstrap:

```bash
# 1. Create a user and capture the access token
ACCESS_TOKEN=$(curl -sS http://localhost:3333/api/v1/user \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

echo "Access token: $ACCESS_TOKEN"

# 2. Get a Bearer JWT
AUTH_TOKEN=$(curl -sS -X POST http://localhost:3333/api/v1/auth/anonymous \
  -H "Content-Type: application/json" \
  -d "{\"accessToken\":\"$ACCESS_TOKEN\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['authToken'])")

# 3. Import seed activities
curl -sS -X POST http://localhost:3333/api/v1/import \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d @docker/seed-data.json

# 4. Update .env with the new token
# Replace GHOSTFOLIO_ACCESS_TOKEN=... line in .env with:
#   GHOSTFOLIO_ACCESS_TOKEN=<the ACCESS_TOKEN from step 1>
# Then restart the agent:
docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env up -d gf-agent
```

### 1.4 Test the Agent

```bash
curl -N -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"How is my portfolio doing ytd?","thread_id":"test-1"}'
```

You should see SSE events: `thinking` → `tool_call` → `tool_result` → `synthesis` → `done`.

### 1.5 Stop Everything

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env down
```

Add `-v` to also destroy the Postgres volume (full reset — requires re-seeding).

### 1.6 Rebuild Agent Only (after code changes)

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env up -d --build agent
```

---

## 2. Production Environment (Railway)

### 2.1 URLs

| Service     | URL                                                              |
|-------------|------------------------------------------------------------------|
| Ghostfolio  | `https://ghostfolio-production-61c8.up.railway.app`              |
| Agent       | `https://agent-production-d1f1.up.railway.app`                   |
| Agent chat  | `https://agent-production-d1f1.up.railway.app/api/agent/chat`    |

### 2.2 Verify Health

```bash
curl -s https://ghostfolio-production-61c8.up.railway.app/api/v1/health
curl -s https://agent-production-d1f1.up.railway.app/health
```

### 2.3 Deploy to Railway

```bash
# Agent (from repo root)
npx @railway/cli up --service agent --ci --path-as-root --message "deploy agent" agent

# Ghostfolio (from repo root)
npx @railway/cli up --service ghostfolio --ci --message "deploy ghostfolio"
```

### 2.4 Set Variables

```bash
npx @railway/cli variables set KEY=VALUE --service agent
```

See `Docs/reference/railway.md` for the full variable list.

### 2.5 Seed Data on Production

Production may reject `dataSource: "YAHOO"` symbols. Use the MANUAL transform:
- Convert `dataSource` from `YAHOO` to `MANUAL`
- Replace each symbol with a deterministic UUID

Full details in `Docs/reference/railway.md` → "Hosted Bootstrap + Import".

---

## 3. Key Files

| File | Purpose |
|------|---------|
| `.env` | Local environment variables (gitignored — never commit) |
| `docker/docker-compose.yml` | Core stack: postgres, redis, ghostfolio |
| `docker/docker-compose.agent.yml` | Agent overlay (adds `gf-agent` service) |
| `docker/seed-data.json` | 26 activities across 6 asset types for testing |
| `agent/Dockerfile` | Agent container definition |
| `agent/main.py` | FastAPI entrypoint |
| `Docs/reference/railway.md` | Full Railway deployment runbook |
| `Docs/reference/demo.md` | Demo script and validation checklist |

---

## 4. Common Pitfalls and Fixes

### Network Mismatch (containers can't talk to each other)

**Symptom:** Agent returns `API_ERROR` on every query.

**Cause:** Running docker compose with different `-f` flags or project names creates separate networks.

**Fix:**
```bash
# Nuclear cleanup
docker rm -f gf-agent ghostfolio gf-postgres gf-redis
docker network prune -f

# Restart with the single canonical command
docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env up -d --build
```

**Prevention:** Always use the full command from section 1.1. Never run `docker compose up` from inside the `docker/` directory.

### Stale Access Token

**Symptom:** Agent returns `AUTH_FAILED` or Ghostfolio gives `401`/`403`.

**Cause:** The `GHOSTFOLIO_ACCESS_TOKEN` in `.env` doesn't match any user in the current Postgres database (happens after a volume reset).

**Fix:** Re-run the seed script from section 1.3 and update `.env` with the new token.

### Port Already in Use

**Symptom:** `Bind for 0.0.0.0:3333 failed: port is already allocated`

**Fix:**
```bash
# Find what's using the port
lsof -i :3333
# Kill it or stop the other container
docker rm -f <container_name>
```

### Orphaned Volumes Wasting Disk

**Symptom:** `docker volume ls` shows old volumes like `ghostfolio_postgres`, `ghostfolio_dev_postgres`.

**Fix:**
```bash
docker volume rm ghostfolio_postgres ghostfolio_dev_postgres
# Or prune all unused volumes (careful — destroys data)
docker volume prune -f
```

### Agent Shows "unhealthy" but Works Fine

**Symptom:** `docker ps` shows `gf-agent` as `(unhealthy)` but `curl localhost:8000/health` returns 200.

**Cause:** The agent's Docker image (`python:3.11-slim`) doesn't include `curl`, so the healthcheck command always fails.

**Fix:** This is cosmetic. The agent works. To fix the status display, you could install curl in the Dockerfile or switch the healthcheck to use `python -c "import urllib.request; ..."`.

---

## 5. Cleanup Checklist

Run periodically to keep your environment lean:

```bash
# 1. Stop all project containers
docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env down

# 2. Remove dangling images
docker image prune -f

# 3. Remove orphaned volumes (only if you're ok re-seeding)
docker volume prune -f

# 4. Remove orphaned networks
docker network prune -f

# 5. Verify clean state
docker ps -a          # Should show nothing project-related
docker volume ls      # Only ghostfolio-development_postgres if you kept it
docker network ls     # Only default bridge/host/none
```

---

## 6. Quick Reference Card

```
START:    docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env up -d --build
STOP:     docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env down
REBUILD:  docker compose -f docker/docker-compose.yml -f docker/docker-compose.agent.yml --env-file .env up -d --build agent
LOGS:     docker logs gf-agent --tail 50 -f
RESET:    ... down -v  (destroys DB — must re-seed)
HEALTH:   curl localhost:3333/api/v1/health && curl localhost:8000/health
TEST:     curl -N -X POST localhost:8000/api/agent/chat -H "Content-Type: application/json" -d '{"query":"How is my portfolio?","thread_id":"t1"}'
```
