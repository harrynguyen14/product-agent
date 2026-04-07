# react_skill — ReAct Pattern: Reasoning + Acting

## Overview

ReAct (Yao et al., 2022) interleaves **Thought** (explicit reasoning) and **Action** (tool calls) in a loop, with **Observation** (tool output) feeding back into the next Thought. This allows agents to adaptively gather information rather than committing to a single tool call.

```
Thought → Action → Observation → Thought → Action → Observation → ... → Final Answer
```

---

## Where ReAct is Applied in This System

| Component | ReAct role | Loop type |
|-----------|-----------|-----------|
| `SearchAgent` | Iterative web search with query refinement | Tool-based loop (`ReActLoop`) |
| `RetrieveAgent` | Iterative vector retrieval with query reformulation | Tool-based loop (`ReActLoop`) |
| `Planner` | Pre-plan reasoning + post-failure observation | Thought-only (no external tools) |

---

## ReActLoop — Shared Engine

**File:** [actions/react_loop.py](../actions/react_loop.py)

```python
loop = ReActLoop(
    action=llm_action,      # LLMAction with injected LLM
    tools=tools,            # list[BaseTool]
    max_steps=5,            # maximum Thought/Action cycles
    system_msg=system,      # skill content + base system
)
result = await loop.run(goal=instruction, context=upstream_str)
```

### ReActResult fields

| Field | Type | Description |
|-------|------|-------------|
| `answer` | `str` | Final answer from the loop |
| `steps` | `int` | Number of Thought/Action cycles used |
| `trajectory` | `list[ReActStep]` | Full step-by-step trace |
| `stopped_by` | `str` | `"final_answer"` \| `"max_steps"` \| `"error"` |

### ReActStep fields

| Field | Type | Description |
|-------|------|-------------|
| `thought` | `str` | LLM's reasoning at this step |
| `action_tool` | `str` | Tool name called |
| `action_arg` | `str` | Argument passed to tool |
| `observation` | `str` | Tool's return value |
| `is_final` | `bool` | True if this step produced Final Answer |
| `final_answer` | `str` | Content of Final Answer if `is_final` |

---

## LLM Output Format Required

The LLM **must** follow this format at every step:

```
Thought: <reasoning about current state and next action>
Action: tool_name(query or argument)
```

or to terminate:

```
Thought: <reasoning that sufficient information has been gathered>
Final Answer: <complete answer to the original goal>
```

Rules enforced by the system prompt:
- Never skip `Thought:` before `Action:` or `Final Answer:`
- Never emit two `Action:` lines in one step
- Use `Final Answer:` only when information is sufficient

---

## SearchAgent — ReAct Config

```python
SearchAgent(
    tools=[web_search_tool],
    max_react_steps=5,      # default: 5
)
```

**Typical trajectory:**

```
Thought: Need to find AI coding tools market share. Start broad.
Action: web_search(AI coding tools market share 2026)
Observation: [3 results — general, no specific figures]

Thought: Results too vague. Need numbers for specific tools.
Action: web_search(Claude Code vs Cursor user adoption Q1 2026 statistics)
Observation: [5 results — includes percentage figures and source links]

Thought: Have enough data. Both tools covered with figures.
Final Answer: Claude Code holds ~18% market share...
```

**When ReAct adds value over single-call:**
- Initial query returns vague/general results → refine
- Missing data for a specific sub-topic → targeted follow-up search
- First result is outdated → search with explicit date range

---

## RetrieveAgent — ReAct Config

```python
RetrieveAgent(
    retrieve_fn=my_fn,
    max_react_steps=3,      # default: 3 (retrieval is cheaper)
)
```

**Typical trajectory:**

```
Thought: Query "authentication" too broad. Scores all below 0.6.
Action: retrieve(JWT token validation middleware implementation)
Observation: [8 chunks] (score=0.91) ... (score=0.88) ...

Thought: Scores high and content relevant. Sufficient.
Final Answer: The retrieved documents show that JWT validation...
```

**Score threshold guidance:**
- ≥ 0.8 — highly relevant, likely sufficient
- 0.6–0.8 — relevant but may need one more query
- < 0.6 — low relevance, reformulate query

**`_make_retrieve_tool` wraps `retrieve_fn`** as a `BaseTool` so `ReActLoop` can call it uniformly.

---

## Planner — ReAct Integration

The Planner does **not** use `ReActLoop` (no external tools), but adds two internal ReAct reasoning steps:

### Step 1: Pre-plan Thought (`_react_think`)

Called **once before the first WritePlan attempt**.

```
Thought: Goal involves comparing 3 tools. Need search + analyze tasks.
         web_search_tool is available. No retrieve_fn registered.
         Plan should run 2 search tasks in parallel then merge.
Conclusion: Use parallel search → summarize → analyze → validate pattern.
```

This conclusion is appended to `_history`, giving `WritePlan` strategic context.

### Step 2: Post-failure Observation (`_react_observe`)

Called **after every plan failure** (validation error or user rejection).

```
# After validation error:
Thought: Plan had circular dependency: task 3 depended on task 4 which depended on task 3.
Fix: Move the summarize task after both search tasks with dependent_task_ids: ["1","2"].

# After user rejection:
Thought: User said plan is missing a validate step.
Fix: Add task_type=validate as the final task depending on the report task.
```

This fix-instruction is appended to history, giving `WritePlan` a concrete directive.

### Injecting a separate LLM for ReAct reasoning

By default the Planner reuses `WritePlan`'s LLM for ReAct thoughts. A lighter/faster model can be injected:

```python
react_action = LLMAction()
react_action.set_llm(fast_llm)   # e.g. haiku-class model

planner = Planner(
    write_plan=write_plan,
    react_llm=react_action,       # optional — defaults to write_plan's LLM
)
```

---

## Configuration Reference

| Parameter | Where | Default | Effect |
|-----------|-------|---------|--------|
| `max_react_steps` | `SearchAgent` | 5 | Max Thought/Action cycles |
| `max_react_steps` | `RetrieveAgent` | 3 | Max retrieve iterations |
| `react_llm` | `Planner` | `None` (reuses WritePlan LLM) | Separate LLM for reasoning |

---

## Logging

All three components emit structured logs:

```python
# SearchAgent / RetrieveAgent
logger.info("search_react_done",  steps=N, stopped_by="final_answer", actions=[...])
logger.info("retrieve_react_done", steps=N, stopped_by="final_answer", queries=[...])

# Planner
logger.info("react_think",   thought="...", conclusion="...")
logger.info("react_observe", thought="...", fix="...")
```

Use these to monitor how many ReAct cycles are being consumed and whether agents are hitting `max_steps`.

---

## Related

- [actions/react_loop.py](../actions/react_loop.py) — shared ReAct engine
- [agents/search_agent.py](../agents/search_agent.py) — ReAct search implementation
- [agents/retrieve_agent.py](../agents/retrieve_agent.py) — ReAct retrieval implementation
- [plan/planer.py](../plan/planer.py) — Planner with pre/post ReAct reasoning
- [skills/search_skill.md](search_skill.md) — search quality guidelines
- [skills/retrieve_skill.md](retrieve_skill.md) — retrieval quality guidelines
- [skills/plan_skill.md](plan_skill.md) — planning guidelines
