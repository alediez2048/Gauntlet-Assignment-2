# Skill: Docker & Service Health Monitor

Check health of all Docker containers and application services.

## When to Use

User says: "check services", "health check", "is everything running", "docker status", "what's running"

## Workflow

### Step 1: Docker Container Status

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null
```

Expected containers for local dev:

| Container       | Image              | Port | Health  |
| --------------- | ------------------ | ---- | ------- |
| gf-postgres-dev | postgres:15-alpine | 5432 | healthy |
| gf-redis-dev    | redis:alpine       | 6379 | healthy |

If containers are not running:

```bash
docker compose -f docker/docker-compose.dev.yml --env-file .env up -d
```

### Step 2: Port Scan

Check all application ports:

```bash
lsof -iTCP:3333 -sTCP:LISTEN -P 2>/dev/null || echo "Port 3333: FREE (NestJS not running)"
lsof -iTCP:4200 -sTCP:LISTEN -P 2>/dev/null || echo "Port 4200: FREE (Angular not running)"
lsof -iTCP:5432 -sTCP:LISTEN -P 2>/dev/null || echo "Port 5432: FREE (PostgreSQL not running)"
lsof -iTCP:6379 -sTCP:LISTEN -P 2>/dev/null || echo "Port 6379: FREE (Redis not running)"
lsof -iTCP:8000 -sTCP:LISTEN -P 2>/dev/null || echo "Port 8000: FREE (Agent not running)"
```

### Step 3: Application Health Endpoints

```bash
# NestJS API
curl -sf http://localhost:3333/api/v1/info | head -1 && echo " ← NestJS OK" || echo "NestJS: DOWN"

# FastAPI Agent
curl -sf http://localhost:8000/health && echo " ← Agent OK" || echo "Agent: DOWN"

# Redis connectivity (via Docker)
docker exec gf-redis-dev redis-cli PING 2>/dev/null || echo "Redis: UNREACHABLE"

# PostgreSQL connectivity (via Docker)
docker exec gf-postgres-dev pg_isready 2>/dev/null || echo "PostgreSQL: UNREACHABLE"
```

### Step 4: Railway Production Health (Optional)

```bash
curl -sf https://ghostfolio-production-61c8.up.railway.app/api/v1/health || echo "Railway Ghostfolio: DOWN"
curl -sf https://agent-production-d1f1.up.railway.app/health || echo "Railway Agent: DOWN"
```

### Step 5: Report Dashboard

```
SERVICE HEALTH DASHBOARD
========================
Docker Containers:
  PostgreSQL (gf-postgres-dev)  [status]
  Redis (gf-redis-dev)          [status]

Application Services:
  NestJS API (port 3333)        [status]
  FastAPI Agent (port 8000)     [status]
  Angular Client (port 4200)    [status]

Railway Production:
  Ghostfolio                    [status]
  Agent                         [status]
```

## Common Issues

| Symptom                   | Diagnosis                      | Fix                           |
| ------------------------- | ------------------------------ | ----------------------------- |
| Docker containers missing | Docker Desktop not running     | Start Docker Desktop          |
| Redis password errors     | Homebrew Redis conflicting     | `brew services stop redis`    |
| Port 3333 held by zombie  | Previous crash                 | `kill -9 <PID>` or reboot     |
| Agent import error        | Wrong directory                | Run uvicorn from project root |
| Multiple Redis on 6379    | Homebrew + Docker both running | Stop Homebrew Redis           |
