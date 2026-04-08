# plan_skill — Task Planning and Decomposition

## Purpose

Guide the planning system (`Planner` + `WritePlan` + `DecomposeAgent`) to produce a high-quality `Plan` — with correct dependency ordering, appropriate task types, and the right level of granularity. This skill is the **entry point** of every pipeline.

---

## Planning Architecture

```
goal (user input)
     ↓
 Planner.run()
     ├── InventoryAgent   → scans available tools/skills/MCP
     ├── Clarify          → clarifies requirements (optional)
     └── WritePlan loop
           ├── LLM generates plan JSON
           ├── PlanValidator checks validity
           ├── AskReview → user confirm / reject + feedback
           └── (retry if rejected, up to max_retries=3)
     ↓
  Plan (list of Task objects)
     ↓
  ActionGraph executes in parallel layers
```

**Key classes:**

| Class | File | Role |
|-------|------|------|
| `Planner` | [plan/planer.py](../plan/planer.py) | Main orchestrator |
| `WritePlan` | [plan/write_plan.py](../plan/write_plan.py) | LLM plan generation |
| `Plan` | [plan/model.py](../plan/model.py) | Data container for tasks |
| `Task` | [plan/model.py](../plan/model.py) | Single executable unit |
| `DecomposeAgent` | [agents/decompose_agent.py](../agents/decompose_agent.py) | Mid-pipeline task decomposition |
| `InventoryAgent` | [agents/inventory_agent.py](../agents/inventory_agent.py) | Tool/skill discovery |

---

## Task Types and When to Use Them

From [plan/task.py](../plan/task.py) — `WritePlan` may only use these types:

| TaskType | Description | Handled by |
|----------|-------------|------------|
| `decompose` | Break a large task into subtasks | `DecomposeAgent` |
| `search` | Search the web for information | `SearchAgent` |
| `retrieve` | Fetch from vector store / database | `RetrieveAgent` |
| `read` | Read a specific file, document, or URL | `ReadAgent` |
| `analyze` | Analyze collected data | `AnalyzeAgent` |
| `synthesize` | Merge multiple sources into one | `SynthesizeAgent` |
| `summarize` | Summarize content | `SummarizeAgent` |
| `report` | Generate final report (ReportOutput) | `ReportAgent` |
| `validate` | Quality-check output | `ValidateAgent` |
| `skill` | Invoke a registered skill | SkillAgent |
| `tool` | Call a specific tool / API | ToolAgent |
| `mcp` | Call an MCP server | MCPAgent |

---

## Standard Task JSON Structure

`WritePlan` produces a JSON list; each element has exactly 4 fields:

```json
[
  {
    "task_id": "1",
    "dependent_task_ids": [],
    "instruction": "Search AI agent tools market data for Q1 2026",
    "task_type": "search"
  },
  {
    "task_id": "2",
    "dependent_task_ids": ["1"],
    "instruction": "Summarize search results, preserve all statistics and sources",
    "task_type": "summarize"
  },
  {
    "task_id": "3",
    "dependent_task_ids": ["2"],
    "instruction": "Write a detailed table report from the summary",
    "task_type": "skill"
  },
  {
    "task_id": "4",
    "dependent_task_ids": ["3"],
    "instruction": "Validate report accuracy and completeness",
    "task_type": "validate"
  }
]
```

**`task_id` convention:** incrementing integers (`"1"`, `"2"`…) or short descriptive names (`"search_market"`, `"summarize_1"`).

---

## Principles of a Good Plan

### 1. Correct dependency ordering

```
# Correct — clear data flow
search → summarize → analyze → report → validate

# Wrong — analyze has no data yet
analyze → search → summarize
```

### 2. Maximum 7 tasks (default max_tasks)

| Task count | Assessment |
|------------|-----------|
| 1–3 | Appropriate for simple questions |
| 4–6 | Optimal for most research tasks |
| 7 | Limit — only when truly necessary |
| >7 | Invalid — `PlanValidator` will reject |

### 3. Parallelise where possible

Tasks with no dependencies run in parallel automatically via `ActionGraph`:

```json
[
  {"task_id": "s1", "dependent_task_ids": [], "task_type": "search", ...},
  {"task_id": "s2", "dependent_task_ids": [], "task_type": "search", ...},
  {"task_id": "s3", "dependent_task_ids": [], "task_type": "read",   ...},
  {"task_id": "merge", "dependent_task_ids": ["s1","s2","s3"], "task_type": "synthesize", ...}
]
```

### 4. Short, atomic instructions

| Good | Poor |
|------|------|
| `"Search Cursor IDE pricing in 2025"` | `"Research everything about Cursor"` |
| `"Summarize search results, keep all figures"` | `"Do something with the results"` |
| `"Analyze market share trends from data"` | `"Analyze, synthesize, and write a report"` |

### 5. Always end with `validate`

Every plan should have a `validate` task as the final step so `ValidateAgent` checks quality before delivery.

---

## Context Injected by Planner into WritePlan

`Planner` injects `STRUCTURAL_CONTEXT` on every `WritePlan` call:

```
## User Requirement
<original goal>

## Conversation History
<clarify history + user feedback>

## Available Components
<InventoryAgent output: registered tools/skills/MCP>

## Current Plan
<existing plan if modifying>
```

`WritePlan` uses this context + `PROMPT_TEMPLATE` to produce a plan that matches the **exact tools available**.

---

## Review Loop and Feedback Handling

```
WritePlan generates plan
      ↓
PlanValidator checks (valid JSON? unique task_ids? within max_tasks?)
      ↓ valid
AskReview shows plan to user
      ↓
  ┌── User confirms → update Plan, exit loop
  └── User rejects + feedback → append feedback to history → WritePlan again
                                 (up to max_retries=3 attempts)
```

When a plan is rejected, **user feedback is appended to `_history`**, so the next `WritePlan` call "remembers" the rejection reason and self-corrects.

---

## DecomposeAgent vs WritePlan — Key Differences

| | `WritePlan` | `DecomposeAgent` |
|-|-------------|-----------------|
| When it runs | Start of pipeline, before execution | Mid-pipeline, when one task is too large |
| Output | `Plan` object (list of `Task`) | `AgentResult` containing subtask JSON list |
| User review | Yes (confirm/reject) | No (automatic) |
| Max tasks | 7 (configurable) | 2–5 |
| Context | Full inventory + conversation history | Upstream results + instruction |

---

## Plan Quality Checklist

Before confirming a plan, verify:

```
✓ Each task has a unique task_id
✓ dependent_task_ids reference valid, already-declared task_ids
✓ task_type belongs to the valid TaskType enum
✓ No circular dependencies
✓ Final task is validate
✓ Instructions are specific enough for an agent to execute without asking follow-up questions
✓ Total tasks ≤ 7
```

---

## Full Example Plan for a Research Task

**Goal:** "Analyse and compare popular AI coding tools in 2026"

```json
[
  {
    "task_id": "1",
    "dependent_task_ids": [],
    "instruction": "Search market share and user adoption of Claude Code, Cursor, GitHub Copilot in 2026",
    "task_type": "search"
  },
  {
    "task_id": "2",
    "dependent_task_ids": [],
    "instruction": "Search pricing models and key features of each tool",
    "task_type": "search"
  },
  {
    "task_id": "3",
    "dependent_task_ids": ["1", "2"],
    "instruction": "Summarize search results, preserving all figures and source URLs",
    "task_type": "summarize"
  },
  {
    "task_id": "4",
    "dependent_task_ids": ["3"],
    "instruction": "Analyze competitive trends and differentiators across tools",
    "task_type": "analyze"
  },
  {
    "task_id": "5",
    "dependent_task_ids": ["4"],
    "instruction": "Write a detailed comparison report in Markdown table format",
    "task_type": "skill"
  },
  {
    "task_id": "6",
    "dependent_task_ids": ["5"],
    "instruction": "Validate report: sufficient data, no missing tools, no fabricated facts",
    "task_type": "validate"
  }
]
```

Tasks `1` and `2` run in parallel → merge into `3` → continue sequentially.

---

## Related

- [plan/planer.py](../plan/planer.py) — Planner orchestrator
- [plan/write_plan.py](../plan/write_plan.py) — LLM plan generation
- [plan/model.py](../plan/model.py) — Plan + Task data models
- [plan/task.py](../plan/task.py) — TaskType enum with descriptions
- [agents/decompose_agent.py](../agents/decompose_agent.py) — mid-pipeline decompose
- [agents/inventory_agent.py](../agents/inventory_agent.py) — tool/skill discovery
- [core/runner.py](../core/runner.py) — EnvironmentRunner initialises Planner
- [actions/action_graph.py](../actions/action_graph.py) — parallel plan execution
