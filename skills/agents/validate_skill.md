# validate_skill — Output Quality Validation

## Purpose

Guide `ValidateAgent` to evaluate whether a pipeline's output actually fulfils its task instruction — checking for completeness, accuracy, fabrication, and format compliance — and return a structured `PASS` / `FAIL` verdict with actionable fixes.

---

## When to Use

| Situation | Use this skill |
|-----------|---------------|
| Any pipeline that produces a user-facing output | Yes — always the final task |
| After `writing_skill` or `report_agent` produces a report | Yes |
| After `synthesize_agent` merges contradictory sources | Yes — check contradiction handling |
| Between intermediate tasks (e.g. after `search`) | Only if quality gate is critical |
| As the only task in a plan | No — validate implies there is upstream output |

---

## Position in Pipeline

```
[any agent producing output]
        ↓
   validate_agent  ← this skill — always the final task
        ↓
  PASS → deliver output to user
  FAIL → return error + suggested_fix to runner / retry logic
```

---

## How ValidateAgent Works

`ValidateAgent` receives all upstream outputs merged into a single string, evaluates against the original task instruction, and returns a JSON verdict:

```python
# validate_agent.py — core logic
raw = await action.aask(PROMPT.format(instruction=instruction, output=output_to_validate))
data = json.loads(ResponseParser.parse_json(raw))
```

**Verdict schema:**

```json
{
  "status": "PASS",
  "issues": [],
  "suggested_fix": ""
}
```

or on failure:

```json
{
  "status": "FAIL",
  "issues": [
    "Report missing pricing comparison for Tool B",
    "Executive summary contradicts key findings table"
  ],
  "suggested_fix": "Re-run writing_skill with explicit instruction to include Tool B pricing data"
}
```

**`AgentResult` mapping:**
- `status == "PASS"` → `ok()` returned
- `status == "FAIL"` → `fail()` returned with `error = "; ".join(issues)` and `output = full verdict dict`

---

## Recommended Instruction Patterns

The validate task instruction should directly mirror the original pipeline goal:

```
Validate that the output:
1. Answers the original question: [ORIGINAL GOAL]
2. Contains no fabricated facts (only uses information from upstream sources)
3. [FORMAT-SPECIFIC CHECK — e.g. "includes a comparison table", "has 5+ findings"]
4. [COMPLETENESS CHECK — e.g. "covers all 3 tools mentioned in the goal"]
```

**Good examples:**

```
Validate that the report:
1. Answers: "Compare AI coding tools market share in 2026"
2. Includes data for Claude Code, Cursor, and GitHub Copilot
3. Contains a comparison table with at least pricing and market share columns
4. States confidence level
5. Contains no fabricated statistics
```

```
Validate the summary:
1. Captures all key findings from the upstream analysis
2. Does not introduce new claims not present in the analysis
3. Is under 500 words
```

---

## Validation Checklist by Output Type

### For `writing_skill` / `report_agent` output:

| Check | What to verify |
|-------|---------------|
| Goal coverage | All entities/topics from the goal are addressed |
| No fabrication | All statistics have a traceable upstream source |
| Table completeness | No empty cells without "N/A" justification |
| Contradiction | Executive summary aligns with findings table |
| Confidence stated | Report includes a confidence/reliability rating |
| Language | Output is in Vietnamese (writing_skill only) |

### For `analyze_agent` / `synthesize_agent` output:

| Check | What to verify |
|-------|---------------|
| Findings grounded | Each `key_findings` item is in the upstream input |
| Contradictions surfaced | Conflicting sources are noted, not silently merged |
| Gaps explicit | `gaps` / `uncertainties` populated honestly |

---

## Retry Integration

When `ValidateAgent` returns `fail()`, the runner can use `suggested_fix` to retry:

```
Runner checks AgentResult.kind == "failure"
     ↓
Reads error (issues list) and output["suggested_fix"]
     ↓
Appends fix instruction to the upstream task's instruction
     ↓
Re-runs the failed task (up to max_retries times)
```

The `max_retries` setting in `AppConfig` (default: 3) controls how many validation-retry cycles are allowed.

---

## Quality Principles

1. **Validate against the original goal** — not against what the output claims to do
2. **Issues must be specific and actionable** — "report is incomplete" is not useful; "report missing pricing for Tool B" is
3. **`suggested_fix` is mandatory on FAIL** — an actionable suggestion enables automated retry
4. **Do not hallucinate issues** — only raise issues that are clearly evident in the output
5. **PASS with caveats** — if output is acceptable but imperfect, PASS and include caveats in `issues` (non-blocking notes)
6. **Always the last task** — `validate` should have the highest `task_id` and depend on all deliverable tasks

---

## Related

- [agents/validate_agent.py](../agents/validate_agent.py) — implementation
- [agents/report_agent.py](../agents/report_agent.py) — primary output being validated
- [skills/writing_skill.md](writing_skill.md) — writing output that must be validated
- [core/runner.py](../core/runner.py) — `max_retries` configuration for retry logic
- [schemas/agent_result.py](../schemas/agent_result.py) — `AgentSuccess` / `AgentFailure` contract
- [plan/task.py](../plan/task.py) — `TaskType.validate`
