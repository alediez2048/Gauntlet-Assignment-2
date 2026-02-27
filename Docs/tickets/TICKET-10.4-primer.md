# TICKET-10.4 Primer: Citations & Confidence Scoring

**For:** New agent session
**Project:** AgentForge - Ghostfolio + AI Agent Integration
**Date:** Feb 26, 2026
**Previous work:** TICKET-10.3 core agent components completed (tool registry, multi-step orchestrator, chain-of-thought). Commit `f734493c5` on `main`.

---

## What Is This Ticket?

TICKET-10.4 implements the "structured responses with citations and confidence" requirement from the Output Formatter component in the PRD. Every agent response now includes:

- **Citations** — source attribution linking specific claims to the tool data points that produced them
- **Confidence scores** — a reliability indicator (0.0-1.0) computed from tool execution signals

Both are built **deterministically from tool results** (not by parsing LLM output), and rendered in the frontend as a colored confidence badge and collapsible sources list.

### Why It Matters

- **Transparency:** Users can see exactly which tool produced each number in the response.
- **Trust calibration:** The confidence badge (green/yellow/red) immediately communicates how reliable the analysis is.
- **Auditability:** Citations create a verifiable chain from narrative claims back to raw data.
- **Graceful degradation:** When tools fail, confidence drops visibly and citations narrow to successful results only.

---

## What Was Done

### Backend (Python)

**1. State Schema (`agent/graph/state.py`)**

- Added `Citation` TypedDict with fields: `label`, `tool_name`, `display_name`, `field`, `value`
- Added `citations: list[Citation]` and `confidence: float | None` to `FinalResponse`

**2. Citation Builder (`agent/graph/nodes.py`)**

- `_TOOL_DISPLAY_NAMES` — maps tool names to human-readable labels (e.g. "Portfolio Analysis")
- `_extract_tool_data_points()` — per-tool extractors pulling 1-3 key data points:
  - **portfolio**: net performance %, total investment, current value
  - **transactions**: total count, top category
  - **tax**: combined liability, tax year
  - **allocation**: top concentration %, target profile
  - **compliance**: violation count, warning count
  - **market**: total holdings, total market value
- `_build_citations()` — iterates successful tool call records, produces ordered `[1]`, `[2]`, etc.

**3. Confidence Scorer (`agent/graph/nodes.py`)**

- `_compute_confidence()` — deterministic scoring formula (0.0-1.0):
  - Start at 1.0 per tool
  - -0.3 if tool failed
  - -0.1 if data payload empty/minimal
  - -0.1 if retries detected (step_count > len(history))
  - Average across tools, clamped to [0.0, 1.0]

**4. Synthesizer Integration (`agent/graph/nodes.py`)**

- Both single-step and multi-step paths in `make_synthesizer_node()` now call `_build_citations()` and `_compute_confidence()` and include results in `final_response`

**5. Prompt Updates (`agent/prompts.py`)**

- Added citation marker instruction to both `SYNTHESIS_PROMPT` and `MULTI_STEP_SYNTHESIS_PROMPT`:
  "Reference data sources using bracket notation [1], [2] etc. when citing specific numbers."

### Frontend (Angular/TypeScript)

**6. Model (`agent-chat.models.ts`)**

- Added `AgentCitation` interface
- Added `citations?: AgentCitation[]` and `confidence?: number | null` to `AgentChatBlock`

**7. Reducer (`agent-chat.reducer.ts`)**

- Extracts `citations` and `confidence` from the `done` SSE event response
- Attaches them to the assistant block (works for both streamed-token and fallback-message paths)

**8. Component (`agent-chat-panel.component.html` + `.scss`)**

- **Confidence badge** — colored pill below assistant message: green (>=80%), yellow (50-79%), red (<50%)
- **Citations list** — collapsible `<details>` "Sources (N)" section with label, display name, and value per citation
- **Dark theme support** — all new elements have `:host-context(.theme-dark)` variants

---

## Commits

| Hash       | Message                                                       |
| ---------- | ------------------------------------------------------------- |
| `4f6c18f8` | feat: add citations and confidence scoring to agent responses |

## Files Changed

| File                                              | Change                                                                                           |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `agent/graph/state.py`                            | Added `Citation` TypedDict, `citations` + `confidence` to `FinalResponse`                        |
| `agent/graph/nodes.py`                            | `_build_citations()`, `_compute_confidence()`, `_TOOL_DISPLAY_NAMES`, synthesizer populates both |
| `agent/prompts.py`                                | Citation marker instructions in both synthesis prompts                                           |
| `agent/tests/unit/test_citations.py`              | **New** — 18 unit tests for citation builder + confidence scorer                                 |
| `apps/client/.../agent-chat.models.ts`            | `AgentCitation` interface, new fields on `AgentChatBlock`                                        |
| `apps/client/.../agent-chat.reducer.ts`           | Extracts citations/confidence from `done` event                                                  |
| `apps/client/.../agent-chat-panel.component.html` | Confidence badge + collapsible citations list                                                    |
| `apps/client/.../agent-chat-panel.component.scss` | Styles for badge + citations + dark theme                                                        |

## Tests

- **104 automated tests passing** (86 existing + 18 new)
- New test coverage:
  - `TestBuildCitations` (10 tests): all 6 tools, empty/failed/no-data records, multi-tool sequential labels
  - `TestComputeConfidence` (8 tests): empty, all-success, single failure, all-failures, retry penalty, empty data, clamping, mixed results
- Frontend production build passes clean
- Railway deployment verified: both `agent` and `ghostfolio` services deployed and healthy
- Smoke tests confirm citations and confidence appear in `done` SSE event payload

## Deployment

Both services deployed to Railway:

- Agent: `https://agent-production-d1f1.up.railway.app` — rebuilt in ~15s
- Ghostfolio: `https://ghostfolio-production-61c8.up.railway.app` — rebuilt in ~172s
- New hosted user bootstrapped with fresh `GHOSTFOLIO_ACCESS_TOKEN`
- All smoke checks pass: portfolio, transactions, tax, allocation, clarifier, invalid-input error paths

## Verification Evidence

Sample `done` event payload showing citations + confidence:

```json
{
  "response": {
    "category": "analysis",
    "message": "...",
    "citations": [
      {
        "label": "[1]",
        "tool_name": "analyze_portfolio_performance",
        "display_name": "Portfolio Analysis",
        "field": "performance.netPerformancePercentage",
        "value": "0.00%"
      },
      {
        "label": "[2]",
        "tool_name": "analyze_portfolio_performance",
        "display_name": "Portfolio Analysis",
        "field": "performance.totalInvestment",
        "value": "$0.00"
      }
    ],
    "confidence": 1.0
  }
}
```

---

## Time Spent

~1.5 hrs (implementation + tests + deployment + smoke verification)
