# Development Environment Blueprint

## Architecture Overview

```
Browser (https://localhost:4200)
    |
    v
Angular Dev Server (port 4200)
    | proxy.conf.json routes /api/* and /assets/*
    v
NestJS API Server (port 3333)
    |--- /api/v1/agent/* ---> FastAPI Agent (port 8000)
    |                              |
    |                              +--> OpenAI GPT-4o (external)
    |                              +--> LangSmith (external, optional)
    |
    |--- /api/v1/* ------------> Internal NestJS handlers
    |                              |
    |                              +--> PostgreSQL (port 5432)
    |                              +--> Redis (port 6379)
    v
Static files served from dist/apps/client
```

## Port Map

| Service        | Port | Protocol | Process              |
| -------------- | ---- | -------- | -------------------- |
| Angular Client | 4200 | HTTPS    | nx serve client      |
| NestJS API     | 3333 | HTTP     | nx serve api         |
| FastAPI Agent  | 8000 | HTTP     | uvicorn              |
| PostgreSQL     | 5432 | TCP      | Docker (gf-postgres) |
| Redis          | 6379 | TCP      | Docker (gf-redis)    |

## Prerequisites

- Node.js 22+
- Python 3.11+ (current: 3.14)
- Docker Desktop
- Homebrew (macOS)

---

## Quick Start (3 Steps)

### Step 1: Start Infrastructure (Docker)

```bash
# From project root
docker compose -f docker/docker-compose.dev.yml --env-file .env up -d
```

This starts **PostgreSQL** and **Redis** containers only.

Verify they're healthy:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

Expected output:

```
NAMES         STATUS                  PORTS
gf-postgres   Up X minutes (healthy)  0.0.0.0:5432->5432/tcp
gf-redis      Up X minutes (healthy)  0.0.0.0:6379->6379/tcp
```

### Step 2: Start Backend Servers (2 terminals)

**Terminal 1 - NestJS API:**

```bash
npm run start:server
```

Wait for: `Listening at http://0.0.0.0:3333`

**Terminal 2 - FastAPI Agent:**

```bash
source agent/.venv/bin/activate
uvicorn agent.main:app --reload
```

Wait for: `Uvicorn running on http://127.0.0.1:8000`

> **Important:** Run uvicorn from the **project root**, not from `agent/`.
> The imports use `from agent.xxx import ...` so it must be run from the parent directory.

### Step 3: Start Frontend (1 terminal)

**Terminal 3 - Angular Client:**

```bash
npm run start:client
```

Wait for: `Angular Live Development Server is listening on https://localhost:4200`

Open: **https://localhost:4200**

---

## Stopping Everything

```bash
# Stop Docker infrastructure
docker compose -f docker/docker-compose.dev.yml down

# Stop NestJS, Angular, and FastAPI with Ctrl+C in their terminals
```

---

## Common Issues & Fixes

### "EADDRINUSE: address already in use 0.0.0.0:3333"

A previous server process is still holding the port.

```bash
# Find the process
lsof -iTCP:3333 -sTCP:LISTEN -P

# Kill it
kill <PID>

# If kill doesn't work (zombie process), temporarily use another port:
PORT=3334 npm run start:server
# Then update proxy.conf.json to point to 3334 too
```

### "ERR AUTH <password> called without any password configured"

A local Homebrew Redis is running alongside the Docker Redis, both on port 6379.
The local one has no password, but the app sends one.

```bash
# Fix: Stop the Homebrew Redis
brew services stop redis

# Verify only Docker Redis remains
lsof -iTCP:6379 -sTCP:LISTEN -P
# Should show only "com.docker" process
```

To **prevent** this from recurring:

```bash
# Disable Homebrew Redis from auto-starting
brew services stop redis
brew unlink redis
```

### "ModuleNotFoundError: No module named 'agent'"

You're running uvicorn from inside the `agent/` directory. Always run from project root:

```bash
cd /path/to/Gauntlet-Assignment-2
uvicorn agent.main:app --reload
```

### "Agent eval proxy failed: fetch failed"

The NestJS server can't reach the FastAPI agent. Make sure:

1. The agent server is running on port 8000
2. Test: `curl http://localhost:8000/health`

### Docker containers not starting

```bash
# Check Docker Desktop is running, then:
docker compose -f docker/docker-compose.dev.yml --env-file .env up -d

# Check logs if unhealthy:
docker logs gf-postgres
docker logs gf-redis
```

### Database migration issues

```bash
# Run pending migrations
npx prisma migrate deploy

# Reset database (destructive)
npx prisma migrate reset

# Regenerate Prisma client
npx prisma generate
```

---

## Environment Variables (.env)

| Variable                  | Required | Purpose                                   |
| ------------------------- | -------- | ----------------------------------------- |
| `POSTGRES_DB`             | Yes      | Database name                             |
| `POSTGRES_USER`           | Yes      | Database user                             |
| `POSTGRES_PASSWORD`       | Yes      | Database password                         |
| `DATABASE_URL`            | Yes      | Full Postgres connection string           |
| `REDIS_HOST`              | Yes      | Redis host (localhost for dev)            |
| `REDIS_PORT`              | Yes      | Redis port (6379)                         |
| `REDIS_PASSWORD`          | Yes      | Redis password (must match Docker config) |
| `ACCESS_TOKEN_SALT`       | Yes      | NestJS auth salt                          |
| `JWT_SECRET_KEY`          | Yes      | JWT signing key                           |
| `OPENAI_API_KEY`          | Yes      | OpenAI API key for agent                  |
| `GHOSTFOLIO_ACCESS_TOKEN` | Yes      | Agent's auth token for Ghostfolio API     |
| `LANGSMITH_API_KEY`       | No       | LangSmith tracing (optional)              |

---

## Docker Compose Files

| File                           | Purpose                                    | When to Use                     |
| ------------------------------ | ------------------------------------------ | ------------------------------- |
| `docker-compose.dev.yml`       | Postgres + Redis only                      | **Local development (default)** |
| `docker-compose.yml`           | Full stack (Ghostfolio + Postgres + Redis) | Production/staging              |
| `docker-compose.agent.yml`     | Adds agent container                       | Full Docker deployment          |
| `docker-compose.agent-dev.yml` | Agent pointing to host Ghostfolio          | Agent Docker testing            |
| `docker-compose.build.yml`     | Build Ghostfolio from source               | Custom builds                   |

---

## Verification Checklist

After starting everything, verify each service:

```bash
# 1. Docker containers healthy
docker ps

# 2. NestJS API responding
curl http://localhost:3333/api/v1/info

# 3. FastAPI agent healthy
curl http://localhost:8000/health

# 4. Redis connected (no password errors in NestJS logs)
# Check Terminal 1 for any RedisCacheService errors

# 5. Angular app loads
# Open https://localhost:4200 - should show portfolio data
```

---

## Claude Code Skills

Custom skills are available in `.claude/skills/` to accelerate common workflows:

| Skill             | Directory                       | Trigger Phrases                    |
| ----------------- | ------------------------------- | ---------------------------------- |
| **dev-start**     | `.claude/skills/dev-start/`     | "start dev", "boot up servers"     |
| **test-all**      | `.claude/skills/test-all/`      | "run tests", "test everything"     |
| **deploy**        | `.claude/skills/deploy/`        | "deploy to railway", "ship it"     |
| **eval-agent**    | `.claude/skills/eval-agent/`    | "run evals", "test agent routing"  |
| **db-migrate**    | `.claude/skills/db-migrate/`    | "migrate database", "add column"   |
| **docker-health** | `.claude/skills/docker-health/` | "check services", "what's running" |

Additionally, **GitNexus** skills are available for code intelligence:

| Skill               | Directory                                  | Purpose                        |
| ------------------- | ------------------------------------------ | ------------------------------ |
| **exploring**       | `.claude/skills/gitnexus/exploring/`       | Navigate unfamiliar code       |
| **impact-analysis** | `.claude/skills/gitnexus/impact-analysis/` | Blast radius before changes    |
| **debugging**       | `.claude/skills/gitnexus/debugging/`       | Trace bugs through call chains |
| **refactoring**     | `.claude/skills/gitnexus/refactoring/`     | Plan safe refactors            |

---

## File Reference

| Config File                                                    | Purpose                     |
| -------------------------------------------------------------- | --------------------------- |
| `.env`                                                         | All environment variables   |
| `apps/client/proxy.conf.json`                                  | Angular dev proxy to NestJS |
| `docker/docker-compose.dev.yml`                                | Dev infrastructure          |
| `prisma/schema.prisma`                                         | Database schema             |
| `agent/requirements.txt`                                       | Python dependencies         |
| `libs/common/src/lib/config.ts`                                | Default port/host constants |
| `apps/api/src/services/configuration/configuration.service.ts` | NestJS env validation       |
