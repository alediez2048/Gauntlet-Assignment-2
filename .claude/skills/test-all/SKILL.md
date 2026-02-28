# Skill: Cross-Framework Test Runner

Run tests across Jest (TypeScript) and Pytest (Python) with unified reporting.

## When to Use

User says: "run tests", "test everything", "check tests", "run all tests"

## Workflow

### Step 1: Determine Scope

Ask or infer what to test:

- **All tests**: Run both Jest and Pytest
- **Agent only**: Run Pytest (unit + integration)
- **Frontend/API only**: Run Jest
- **Eval only**: Run eval dataset (63 cases)
- **Affected only**: Run tests for changed files

### Step 2: Run Jest (TypeScript/JavaScript)

**All Jest tests:**

```bash
npx nx run-many --target=test --parallel=4
```

**Specific project:**

```bash
npx nx test api
npx nx test client
npx nx test common
npx nx test ui
```

**Affected only (based on git changes):**

```bash
npx nx affected --target=test
```

### Step 3: Run Pytest (Python Agent)

**Activate venv first:**

```bash
source agent/.venv/bin/activate
```

**All agent tests:**

```bash
python -m pytest agent/tests/ -v
```

**Unit tests only:**

```bash
python -m pytest agent/tests/unit/ -v
```

**Integration tests only:**

```bash
python -m pytest agent/tests/integration/ -v
```

**Eval runner (63 cases, no LLM, uses keyword_router):**

```bash
python -m pytest agent/tests/eval/test_eval_runner.py -v
```

**Single test file:**

```bash
python -m pytest agent/tests/unit/test_router.py -v
```

### Step 4: Report Results

Summarize results in a table:

| Suite                | Tests | Passed | Failed | Skipped | Time |
| -------------------- | ----- | ------ | ------ | ------- | ---- |
| Jest (api)           | ?     | ?      | ?      | ?       | ?s   |
| Jest (client)        | ?     | ?      | ?      | ?       | ?s   |
| Pytest (unit)        | ?     | ?      | ?      | ?       | ?s   |
| Pytest (integration) | ?     | ?      | ?      | ?       | ?s   |
| Pytest (eval)        | 63    | ?      | ?      | ?       | ?s   |

### Key Test Files Reference

| Test Area         | Location                               |
| ----------------- | -------------------------------------- |
| API unit tests    | `apps/api/src/**/*.spec.ts`            |
| Client unit tests | `apps/client/src/**/*.spec.ts`         |
| Agent unit tests  | `agent/tests/unit/test_*.py`           |
| Agent integration | `agent/tests/integration/test_*.py`    |
| Eval dataset      | `agent/tests/eval/eval_dataset.json`   |
| Eval runner       | `agent/tests/eval/test_eval_runner.py` |
| Test fixtures     | `agent/tests/fixtures/*.json`          |
| Pytest config     | `agent/tests/conftest.py`              |

### Common Failures

| Failure Pattern              | Likely Cause            | Fix                                                     |
| ---------------------------- | ----------------------- | ------------------------------------------------------- |
| `ModuleNotFoundError: agent` | Wrong working directory | Run pytest from project root                            |
| `ConnectionRefusedError`     | Docker not running      | `docker compose -f docker/docker-compose.dev.yml up -d` |
| Eval timeout                 | Slow tool execution     | Check mock client fixtures                              |
| Jest snapshot mismatch       | UI changes              | `npx nx test <project> -- -u` to update snapshots       |
