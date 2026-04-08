# analyze_skill — Rigorous Data Analysis

## Purpose

Guide `AnalyzeAgent` to perform structured analysis on collected information — identifying key findings, patterns, and gaps — and return a typed `AnalysisOutput`. This skill bridges raw data collection and synthesis/reporting.

---

## When to Use

| Situation | Use this skill |
|-----------|---------------|
| Have summarised / read data and need deeper insight | Yes |
| Need to identify patterns or relationships in data | Yes |
| Need to compare multiple data points or sources | Yes — or use `synthesize_agent` if merging sources |
| Just need a shorter version of existing text | No — use `summarize_agent` |
| Need to merge contradictory sources into one view | No — use `synthesize_agent` |

---

## Position in Pipeline

```
search / retrieve / read / summarize
        ↓
   analyze_agent  ← this skill
        ↓
   synthesize_agent (optional — if merging multiple analyses)
        ↓
   report_agent / writing_skill
        ↓
   validate_agent
```

---

## How AnalyzeAgent Works

`AnalyzeAgent` uses `ActionNode` with `AnalysisOutput` schema, ensuring typed structured output:

```python
# analyze_agent.py — core logic
node = ActionNode(name=self.name, schema_cls=AnalysisOutput)
node.set_action(action)
result = await node.run(PROMPT.format(...), system_msg=SYSTEM)
```

**Output schema** ([schemas/analysis.py](../schemas/analysis.py)):

```python
class AnalysisOutput(BaseModel):
    key_findings: list[str]   # grounded facts from input
    patterns:     list[str]   # recurring themes or relationships
    gaps:         list[str]   # missing data or unanswerable questions
    summary:      str         # one-paragraph synthesis
```

The LLM is instructed: **"Only use facts present in the input — never fabricate."**

---

## Recommended Instruction Patterns

```
Analyze [TOPIC] from the data provided.
Identify: key findings, trends, anomalies, and data gaps.
Focus on: [specific dimension — e.g. pricing, performance, adoption]
```

**Good examples:**

```
Analyze competitive positioning of AI coding tools based on market share data.
Identify pricing trends, growth anomalies, and gaps in enterprise adoption data.
```

```
Analyze the performance benchmark results.
Identify which models consistently outperform others and on which task types.
```

**Poor examples (avoid):**

```
Analyze everything.
Tell me what you think about the data.
```

---

## AnalysisOutput Fields — Usage Guide

| Field | What to put here | Used by downstream |
|-------|-----------------|-------------------|
| `key_findings` | Specific, verifiable facts from input | `ReportAgent` → `key_findings` |
| `patterns` | Recurring themes, correlations, trends | `SynthesizeAgent`, `ReportAgent` |
| `gaps` | Questions the data cannot answer | `ReportAgent` → `knowledge_gaps` |
| `summary` | 1-paragraph narrative of the analysis | `SummarizeAgent`, `writing_skill` |

---

## System Prompt Used

```
You are a research analysis agent. Analyze information rigorously.
Only use facts present in the input — never fabricate.
```

This system message is injected by `AnalyzeAgent` on every call. Do not override it in the task instruction.

---

## Parallel Analysis Pattern

When the plan has multiple data sources, analyse them in parallel then synthesise:

```json
[
  {
    "task_id": "a1",
    "task_type": "analyze",
    "instruction": "Analyze market share trends from search results",
    "dependent_task_ids": ["search_1"]
  },
  {
    "task_id": "a2",
    "task_type": "analyze",
    "instruction": "Analyze pricing structures from collected data",
    "dependent_task_ids": ["search_2"]
  },
  {
    "task_id": "synth",
    "task_type": "synthesize",
    "instruction": "Merge both analyses into a unified competitive overview",
    "dependent_task_ids": ["a1", "a2"]
  }
]
```

---

## Quality Principles

1. **Evidence-bound** — every `key_findings` item must be traceable to a specific upstream fact
2. **Distinguish finding vs. inference** — findings are observed; patterns may be inferred but must be flagged
3. **Gaps are first-class** — populating `gaps` honestly is as important as populating `key_findings`
4. **No redundancy with summarize** — if you only need shorter text, use `summarize_agent`; `analyze_agent` adds analytical value
5. **One analytical dimension per task** — do not bundle "pricing analysis" and "feature analysis" into one task

---

## Related

- [agents/analyze_agent.py](../agents/analyze_agent.py) — implementation
- [schemas/analysis.py](../schemas/analysis.py) — `AnalysisOutput` schema
- [agents/summarize_agent.py](../agents/summarize_agent.py) — lighter alternative for plain summarisation
- [agents/synthesize_agent.py](../agents/synthesize_agent.py) — merges multiple AnalysisOutputs
- [agents/report_agent.py](../agents/report_agent.py) — consumes analysis for final report
- [plan/task.py](../plan/task.py) — `TaskType.analyze`
