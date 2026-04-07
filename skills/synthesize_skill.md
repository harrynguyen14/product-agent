# synthesize_skill — Multi-Source Knowledge Synthesis

## Purpose

Guide `SynthesizeAgent` to combine multiple upstream results (analyses, summaries, retrieved data) into a single **coherent, unified view** — resolving contradictions, establishing consensus, and flagging remaining uncertainties. Returns a typed `SynthesisOutput`.

---

## When to Use

| Situation | Use this skill |
|-----------|---------------|
| Multiple parallel analyses need merging | Yes |
| Two or more sources contradict each other | Yes |
| Multiple summaries need unification | Yes |
| Only one upstream source | No — use `analyze_agent` or `summarize_agent` instead |
| Just need shorter text | No — use `summarize_agent` |

---

## Position in Pipeline

```
[analyze_agent × N]  or  [summarize_agent × N]  or  [retrieve_agent × N]
        ↓ (all parallel outputs)
   synthesize_agent  ← this skill
        ↓
   report_agent / writing_skill
        ↓
   validate_agent
```

---

## How SynthesizeAgent Works

`SynthesizeAgent` uses `ActionNode` with `SynthesisOutput` schema:

```python
# synthesize_agent.py — core logic
upstream_str = "\n\n---\n\n".join(
    f"Source [{k}]:\n{v}" for k, v in upstream.items()
)
result = await node.run(PROMPT.format(instruction=instruction, upstream=upstream_str))
```

Sources are labelled `Source [task_id]` so the LLM can reason about provenance.

**Output schema** ([schemas/synthesis.py](../schemas/synthesis.py)):

```python
class SynthesisOutput(BaseModel):
    unified_result:   str         # coherent merged narrative
    consensus_points: list[str]   # facts all sources agree on
    contradictions:   list[str]   # points where sources disagree
    uncertainties:    list[str]   # unresolved or low-confidence points
```

The LLM is instructed: **"Combine multiple sources into a unified, coherent result. Never invent facts."**

---

## Recommended Instruction Patterns

```
Synthesise [N] sources into a unified [TOPIC] overview.
Resolve any contradictions, identify consensus, and flag uncertainties.
Focus on: [specific aspect if needed]
```

**Good examples:**

```
Synthesise market share analysis and pricing analysis into a unified
competitive landscape overview. Flag any contradictions between sources.
```

```
Combine the three research summaries into one coherent view of LLM benchmark performance.
Highlight areas of consensus and note where sources disagree.
```

---

## SynthesisOutput Fields — Usage Guide

| Field | What it contains | Used by downstream |
|-------|-----------------|-------------------|
| `unified_result` | The merged narrative — single source of truth | `ReportAgent`, `writing_skill` |
| `consensus_points` | Facts agreed on by all sources | `ReportAgent` → `key_findings` |
| `contradictions` | Points where sources conflict | `ReportAgent` → `risks`, `ValidateAgent` |
| `uncertainties` | Low-confidence or unresolved points | `ReportAgent` → `knowledge_gaps` |

---

## Handling Contradictions

When sources contradict, `SynthesizeAgent` should:

1. State **both positions** in `contradictions` with source labels
2. **Not arbitrarily pick one** unless one source is clearly more authoritative
3. Surface the contradiction to `ValidateAgent` for review

Example contradiction entry:
```
Source [a1] reports 35% market share; Source [a2] reports 28%. 
Different time periods (Q3 vs Q4 2025) may explain the discrepancy.
```

---

## Multi-Source Merge Pattern

```json
[
  {"task_id": "s1", "task_type": "search",   "dependent_task_ids": [], ...},
  {"task_id": "s2", "task_type": "search",   "dependent_task_ids": [], ...},
  {"task_id": "a1", "task_type": "analyze",  "dependent_task_ids": ["s1"], ...},
  {"task_id": "a2", "task_type": "analyze",  "dependent_task_ids": ["s2"], ...},
  {
    "task_id": "synth",
    "task_type": "synthesize",
    "instruction": "Merge both analyses into a unified competitive overview. Flag contradictions.",
    "dependent_task_ids": ["a1", "a2"]
  }
]
```

`ActionGraph` runs `s1`, `s2` in parallel → `a1`, `a2` in parallel → `synth` receives both.

---

## Quality Principles

1. **Preserve provenance** — the `unified_result` should implicitly reflect where claims came from
2. **Contradictions are not failures** — surface them clearly rather than hiding them
3. **Consensus ≠ truth** — multiple sources agreeing does not guarantee correctness; flag source quality
4. **Uncertainties must be explicit** — do not bury low-confidence inferences in `unified_result`
5. **Minimum two upstream sources** — if only one source exists, skip `synthesize_agent`

---

## Related

- [agents/synthesize_agent.py](../agents/synthesize_agent.py) — implementation
- [schemas/synthesis.py](../schemas/synthesis.py) — `SynthesisOutput` schema
- [agents/analyze_agent.py](../agents/analyze_agent.py) — typical upstream producer
- [agents/summarize_agent.py](../agents/summarize_agent.py) — alternative upstream producer
- [agents/report_agent.py](../agents/report_agent.py) — consumes synthesis for final report
- [actions/action_graph.py](../actions/action_graph.py) — parallel execution enabling multi-source merge
- [plan/task.py](../plan/task.py) — `TaskType.synthesize`
