# Skill: Agent Eval Runner

Run and analyze the agent evaluation suite (63 test cases across 7 eval types).

## When to Use

User says: "run evals", "eval the agent", "test agent routing", "check eval results", "run eval suite"

## Workflow

### Step 1: Determine Scope

- **Full suite**: All 63 cases (default)
- **By category**: happy_path (29), edge_case (11), adversarial (12), multi_step (11)
- **By eval type**: tool_selection, tool_execution, correctness, safety, consistency, edge_case, latency
- **Single case**: By ID (e.g., `hp_portfolio_ytd_01`)

### Step 2A: Run via Pytest (Recommended for CI)

```bash
source agent/.venv/bin/activate

# Full suite
python -m pytest agent/tests/eval/test_eval_runner.py -v

# Single category
python -m pytest agent/tests/eval/test_eval_runner.py -v -k "happy_path"

# Single eval type
python -m pytest agent/tests/eval/test_eval_runner.py -v -k "tool_selection"

# Single case by ID
python -m pytest agent/tests/eval/test_eval_runner.py -v -k "hp_portfolio_ytd_01"
```

### Step 2B: Run via SSE Endpoint (Live Streaming)

**Local agent must be running on port 8000.**

```bash
curl -s -X POST http://localhost:8000/api/agent/eval \
  -H "Content-Type: application/json" -d '{}' 2>&1
```

**On Railway:**

```bash
curl -s -X POST https://agent-production-d1f1.up.railway.app/api/agent/eval \
  -H "Content-Type: application/json" -d '{}' 2>&1
```

### Step 2C: Run via UI (Testing Mode)

1. Open https://localhost:4200
2. Open Agent chat panel (bottom-right FAB)
3. Toggle **Testing** mode
4. Click **Run All Evals**

### Step 3: Analyze Results

Parse SSE output for pass/fail summary. Key events:

- `eval_start` → `{total_cases, categories}`
- `eval_result` → `{id, category, input, results, passed, elapsed_seconds}`
- `eval_done` → `{total, passed, failed, elapsed_seconds, by_category, by_eval_type}`

### Step 4: Report

Format results as:

**Overall:** X/63 passed (Y% pass rate)

**By Category:**

| Category    | Passed | Failed | Rate |
| ----------- | ------ | ------ | ---- |
| happy_path  | ?/29   | ?      | ?%   |
| edge_case   | ?/11   | ?      | ?%   |
| adversarial | ?/12   | ?      | ?%   |
| multi_step  | ?/11   | ?      | ?%   |

**By Eval Type:**

| Type           | Passed | Failed |
| -------------- | ------ | ------ |
| tool_selection | ?      | ?      |
| tool_execution | ?      | ?      |
| correctness    | ?      | ?      |
| safety         | ?      | ?      |
| consistency    | ?      | ?      |
| edge_case      | ?      | ?      |
| latency        | ?      | ?      |

**Failed Cases:** List each failed case ID, input query, and which checks failed.

## Key Files

| File                                   | Purpose                                        |
| -------------------------------------- | ---------------------------------------------- |
| `agent/tests/eval/eval_dataset.json`   | 63 eval cases with expected outputs            |
| `agent/tests/eval/test_eval_runner.py` | Pytest parametrized runner                     |
| `agent/main.py` (POST /api/agent/eval) | SSE streaming endpoint                         |
| `agent/clients/mock_client.py`         | MockGhostfolioClient for deterministic testing |
| `agent/tests/fixtures/`                | JSON fixture data for mock responses           |

## Notes

- Eval uses `keyword_router` (deterministic) + `MockGhostfolioClient` (no LLM, no auth needed)
- Latency threshold: 5 seconds per case
- The eval endpoint does NOT require OpenAI API key or Ghostfolio connection
