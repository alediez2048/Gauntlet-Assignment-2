# Skill: Dev Environment Start

Start all development services in the correct order with health verification.

## When to Use

User says: "start dev", "start servers", "boot up", "start everything"

## Workflow

### Step 1: Check Docker Infrastructure

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null
```

If `gf-postgres-dev` and `gf-redis-dev` are NOT running:

```bash
docker compose -f docker/docker-compose.dev.yml --env-file .env up -d
```

Wait for healthy status:

```bash
docker ps --format '{{.Names}} {{.Status}}' | grep -E 'gf-(postgres|redis)'
```

### Step 2: Check for Port Conflicts

Check ports 3333, 4200, 6379, 8000:

```bash
lsof -iTCP:3333 -sTCP:LISTEN -P 2>/dev/null
lsof -iTCP:4200 -sTCP:LISTEN -P 2>/dev/null
lsof -iTCP:6379 -sTCP:LISTEN -P 2>/dev/null
lsof -iTCP:8000 -sTCP:LISTEN -P 2>/dev/null
```

**Known issue**: Homebrew Redis on port 6379 conflicts with Docker Redis. Fix:

```bash
brew services stop redis
```

**Known issue**: Zombie node process on port 3333. Fix:

```bash
kill $(lsof -iTCP:3333 -sTCP:LISTEN -P -t) 2>/dev/null
```

If kill fails (zombie), use `PORT=3334 npm run start:server` and update `apps/client/proxy.conf.json` target to 3334.

### Step 3: Report Status

Tell the user to start these in 3 separate terminals:

**Terminal 1 - NestJS API:**

```
npm run start:server
```

Wait for: `Listening at http://0.0.0.0:3333`

**Terminal 2 - FastAPI Agent:**

```
source agent/.venv/bin/activate
uvicorn agent.main:app --reload
```

IMPORTANT: Run from **project root**, NOT from `agent/` directory.
Wait for: `Application startup complete`

**Terminal 3 - Angular Client:**

```
npm run start:client
```

Wait for: `Angular Live Development Server is listening on https://localhost:4200`

### Step 4: Verify All Services

```bash
curl -sf http://localhost:3333/api/v1/info | head -1
curl -sf http://localhost:8000/health
# Angular: open https://localhost:4200
```

## Troubleshooting Quick Reference

| Error                           | Cause                          | Fix                                                      |
| ------------------------------- | ------------------------------ | -------------------------------------------------------- |
| EADDRINUSE 3333                 | Previous server still running  | `kill $(lsof -iTCP:3333 -sTCP:LISTEN -P -t)`             |
| ERR AUTH password               | Homebrew Redis conflict        | `brew services stop redis`                               |
| No module 'agent'               | Running uvicorn from wrong dir | Run from project root: `uvicorn agent.main:app --reload` |
| zsh: command not found: uvicorn | venv not activated             | `source agent/.venv/bin/activate`                        |
| Agent proxy failed              | Agent not running on 8000      | Start uvicorn first                                      |
