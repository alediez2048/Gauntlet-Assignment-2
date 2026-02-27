# TICKET-10.3 Primer: Core Agent Component Upgrades

**For:** New agent session
**Project:** AgentForge - Ghostfolio + AI Agent Integration
**Date:** Feb 26, 2026
**Previous work:** TICKET-10.3 production fixes completed (auth gate, LLM router, seed button, NestJS proxy). Commit `82a663b7a` on `main`.

---

## What Is This Ticket?

TICKET-10.3 (core components phase) delivers the three major architectural upgrades required by the PRD's "Core Agent Components" section: a formal tool registry, multi-step orchestration, and chain-of-thought reasoning. These upgrades transform the agent from a single-tool-per-query system into one that can plan and execute multi-tool workflows with visible reasoning.

### Why It Matters

- **Tool Registry:** Replaces fragile manual argument parsing with Pydantic-validated schemas and OpenAI native function calling, eliminating a whole class of runtime errors.
- **Multi-Step Orchestrator:** Enables queries like "full health check" to trigger 3 tools in sequence, with retry logic and partial-failure recovery.
- **Chain-of-Thought:** Makes the agent's routing decisions transparent via SSE "thinking" events, improving user trust and debuggability.

---

## What Was Done

### 1. Compliance Check & Market Data Tools (commit `8acb34baa`)

Completed the 6-tool architecture required by the PRD:

- **`check_compliance`** — screens portfolio for wash sales, pattern day trading, and concentration risk
- **`get_market_data`** — fetches current prices and market metrics for portfolio holdings
- Both tools follow the established async pattern with `ToolResult.ok()`/`ToolResult.fail()` and full error taxonomy mapping

### 2. Formal Tool Registry with Pydantic Schemas (commit `bd443a746`)

- **`agent/tools/schemas.py`** — 6 Pydantic input models (`PortfolioAnalysisInput`, `TransactionCategorizerInput`, `CapitalGainsTaxInput`, `AssetAllocationInput`, `ComplianceCheckInput`, `MarketDataInput`) with `Literal[]` enums and `Field` validators
- **`agent/tools/registry.py`** — `ToolDefinition` dataclass + `TOOL_REGISTRY` dict + `build_openai_function_schemas()` for native function calling
- **Tool executor migration** — `make_tool_executor_node()` now validates args via Pydantic before execution, with graceful fallback to `_default_args_for_tool()` on validation failure
- **Router migration** — `_build_router_callable()` uses OpenAI `tools` parameter instead of manual JSON parsing
- **Persistent checkpointer** — Added SQLite-backed `SqliteSaver` for LangGraph state persistence across turns

### 3. Multi-Step Orchestrator + Chain-of-Thought (commits `9e28bbb6b`, `f734493c5`)

- **`_detect_multi_step()`** — deterministic trigger phrase detection for composite queries ("full health check" -> portfolio + compliance + allocation)
- **`make_orchestrator_node()`** — new graph node that decides after each tool execution: synthesize, continue to next step, retry on failure, or route to error
- **`route_after_orchestrator()`** — conditional edge function for the new orchestrator node
- **Graph topology update** — extended from 6-node to include orchestrator loop: Router -> ToolExecutor -> Validator -> **Orchestrator** -> (Synthesizer | Router | Error)
- **Multi-step synthesis** — `MULTI_STEP_SYNTHESIS_PROMPT` combines results from multiple tools into a single coherent response
- **Chain-of-thought reasoning** — Router node captures `reasoning` field and emits it as SSE "thinking" events; `AgentState` extended with `reasoning` field
- **Priority fix** — multi-step detection takes priority over LLM clarify routing to prevent false clarifications on valid composite queries

---

## Commits

| Hash       | Message                                                                                 |
| ---------- | --------------------------------------------------------------------------------------- |
| `8acb34ba` | feat: add compliance_check and market_data tools to complete 6-tool architecture        |
| `bd443a74` | feat: add formal tool registry with Pydantic schemas and persistent SQLite checkpointer |
| `9e28bbb6` | feat: add multi-step orchestrator and chain-of-thought reasoning                        |
| `f734493c` | fix: multi-step detection takes priority over LLM clarify routing                       |

## Files Changed

| File                                    | Change                                                                                    |
| --------------------------------------- | ----------------------------------------------------------------------------------------- |
| `agent/tools/compliance_checker.py`     | **New** — compliance screening tool                                                       |
| `agent/tools/market_data.py`            | **New** — market data tool                                                                |
| `agent/tools/schemas.py`                | **New** — 6 Pydantic input models                                                         |
| `agent/tools/registry.py`               | **New** — ToolDefinition + TOOL_REGISTRY + OpenAI schema builder                          |
| `agent/graph/nodes.py`                  | Orchestrator node, multi-step detection, Pydantic validation in executor, updated routing |
| `agent/graph/state.py`                  | Added `reasoning`, `step_count`, `tool_plan`, `retry_count` to AgentState                 |
| `agent/graph/builder.py`                | Extended graph topology with orchestrator loop                                            |
| `agent/prompts.py`                      | Added `MULTI_STEP_SYNTHESIS_PROMPT`                                                       |
| `agent/main.py`                         | Router uses OpenAI function calling, synthesizer callable, checkpointer setup             |
| `agent/tests/unit/test_orchestrator.py` | **New** — 12 unit tests for orchestrator + multi-step detection                           |

## Tests

- 86 automated tests passing (66 unit + 20 integration)
- All existing tests unaffected by new additions
- New orchestrator tests cover: single-step success, multi-step continuation, retry logic, max-step cap, failure recovery

## Key Architectural Decisions

1. **Pydantic validation as safety net, not gate** — if schema validation fails, falls back to query-derived defaults rather than rejecting the request
2. **Deterministic multi-step triggers** — phrase matching (not LLM) decides when to use multi-step, ensuring reliability
3. **Orchestrator as state machine** — uses `pending_action` + `step_count` + `tool_plan` to make deterministic routing decisions after each tool execution
4. **Backward-compatible state** — all new AgentState fields are `total=False`, so existing single-step flows work unchanged

---

## Time Spent

~4 hrs (tool completion + registry + orchestrator + CoT + testing)
