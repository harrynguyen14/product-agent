# decompose_skill — Mid-Pipeline Task Decomposition

## Purpose

Guide `DecomposeAgent` to break a single complex task into 2–5 atomic, independently executable subtasks **during pipeline execution**. Unlike `WritePlan` (which plans upfront), `DecomposeAgent` operates mid-pipeline when a task proves too large or multi-faceted to handle in one step.

---

## When to Use

| Situation | Use this skill |
|-----------|---------------|
| A task instruction covers multiple distinct operations | Yes |
| A task is too large for one agent call | Yes |
| Upfront planning failed to anticipate complexity | Yes |
| Task is simple and atomic | No — execute directly |
| Initial plan needs restructuring before execution starts | No — use `WritePlan` / `Planner` |

---

## Position in Pipeline

```
WritePlan (initial plan)
        ↓
   ActionGraph execution
        ↓  [task is too complex]
   decompose_agent  ← this skill
        ↓  [returns subtask list]
   spawned subtasks run in sequence / parallel
        ↓
   continue pipeline...
```

---

## How DecomposeAgent Works

`DecomposeAgent` calls the LLM with the task instruction and upstream context, returning a JSON list of subtasks:

```python
# decompose_agent.py — prompt constraint
"Break this task into 2-5 concrete, executable subtasks.
Each subtask must be atomic and independently actionable."
```

**Output format** (raw JSON, parsed by `ResponseParser`):

```json
[
  {
    "task_id": "1",
    "instruction": "Search for X",
    "task_type": "search"
  },
  {
    "task_id": "2",
    "instruction": "Summarise results from task 1",
    "task_type": "summarize"
  }
]
```

Note: `DecomposeAgent` returns `AgentResult` with `output = list[dict]` — not a `Plan` object. The caller is responsible for integrating subtasks into the execution graph.

---

## DecomposeAgent vs WritePlan — Key Difference

| Aspect | `DecomposeAgent` | `WritePlan` |
|--------|-----------------|-------------|
| When it runs | Mid-pipeline, during execution | Before execution starts |
| Output type | `AgentResult(output=list[dict])` | `Plan` object |
| User review | No — automatic | Yes — confirm/reject loop |
| Max subtasks | 2–5 | Up to 7 (configurable) |
| Context available | Upstream task results | Full inventory + history |
| Dependency tracking | Implicit (sequential) | Explicit `dependent_task_ids` |

---

## Recommended Instruction Patterns

```
Decompose the following task into 2-5 atomic subtasks:
[ORIGINAL TASK INSTRUCTION]

Context available: [brief description of upstream data]
```

**Good decomposition targets:**

```
# Too broad for one agent — decompose it
"Research, analyse, and compare three AI frameworks for production use"

# Becomes:
→ "Search for production benchmarks of Framework A, B, and C"
→ "Search for developer adoption and community activity of each"
→ "Analyse benchmark and adoption data for comparative insights"
→ "Synthesise analysis into a unified comparison"
```

**Already atomic — do not decompose:**

```
"Summarise the search results about pricing"
"Validate that the report contains at least 5 findings"
```

---

## Subtask Design Rules

1. **Atomic** — each subtask should be completable by one agent in one call
2. **2–5 subtasks only** — more than 5 indicates the original task needs replanning, not decomposition
3. **Valid task types** — every subtask must use a type from `TaskType` enum
4. **Natural ordering** — subtasks should reflect natural data flow (collect → process → output)
5. **No circular dependency** — subtask N should not require output from subtask N+1

---

## Full Example

**Original task:** `"Research the latest LLM safety benchmarks and summarise findings"`

**Decomposed subtasks:**

```json
[
  {
    "task_id": "d1",
    "instruction": "Search for LLM safety benchmark results published in 2025-2026",
    "task_type": "search"
  },
  {
    "task_id": "d2",
    "instruction": "Search for academic papers and blog posts on LLM safety evaluation methods",
    "task_type": "search"
  },
  {
    "task_id": "d3",
    "instruction": "Summarise search results from d1 and d2, preserving benchmark names, scores, and sources",
    "task_type": "summarize"
  }
]
```

`d1` and `d2` run in parallel; `d3` depends on both.

---

## Quality Principles

1. **Minimum viable decomposition** — prefer 2–3 subtasks over 5 unless each is genuinely independent
2. **Preserve intent** — the decomposed subtasks must collectively fulfil the original task instruction
3. **Use upstream context** — if upstream data is available, incorporate it into subtask instructions
4. **Fail gracefully** — if JSON parsing fails, `DecomposeAgent` returns `fail()` with raw output; the caller should log and fall back to executing the original task directly
5. **No nested decomposition** — subtasks should not themselves be `decompose` type

---

## Related

- [agents/decompose_agent.py](../agents/decompose_agent.py) — implementation
- [plan/write_plan.py](../plan/write_plan.py) — upfront planning counterpart
- [plan/model.py](../plan/model.py) — `Plan` and `Task` data models
- [plan/task.py](../plan/task.py) — `TaskType.decompose` and all valid subtask types
- [actions/action_graph.py](../actions/action_graph.py) — executes resulting subtasks
- [utils/response_parser.py](../utils/response_parser.py) — parses JSON output from LLM
