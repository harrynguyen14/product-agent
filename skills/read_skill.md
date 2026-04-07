# read_skill — Precise Content Extraction

## Purpose

Guide `ReadAgent` to extract key information from provided content (documents, file text, URL body, upstream raw data) and return only what is relevant to the task instruction. This skill sits between raw content ingestion and analytical processing.

---

## When to Use

| Situation | Use this skill |
|-----------|---------------|
| Content is already available in upstream (fetched, loaded) | Yes |
| Need to read a specific file path or local document | Yes |
| Need to discover content by searching the web | No — use `search_agent` |
| Need to retrieve from a vector store | No — use `retrieve_agent` |
| Content is too large and needs chunking / summarisation | Chain with `summarize_agent` after |

---

## Position in Pipeline

```
search_agent / retrieve_agent / external loader
        ↓
   read_agent  ← this skill
        ↓
   summarize_agent / analyze_agent
        ↓
   synthesize / report / writing_skill
```

---

## How ReadAgent Works

`ReadAgent` receives content from `upstream` (merged values from all dependent task results) and passes it to the LLM with the task instruction:

```python
# read_agent.py — core logic
content = "\n\n".join(str(v) for v in upstream.values())
result  = await action.aask(PROMPT.format(instruction=instruction, content=content))
```

The LLM is instructed to:
- Extract key information **relevant to the task instruction**
- Be precise and **preserve facts and figures**
- Not invent or infer beyond what is in the content

---

## Recommended Instruction Patterns

When `WritePlan` or `DecomposeAgent` creates a `read` task, the instruction should specify:

```
Read the content and extract: [SPECIFIC INFORMATION NEEDED]
Focus on: [aspect / section / data type]
Preserve: [figures / dates / names / URLs if important]
```

**Good examples:**

```
Read the document and extract all pricing tiers and feature limits.
Preserve exact dollar amounts and plan names.
```

```
Read the page content and extract the author, publication date,
and main conclusions. Ignore navigation and footer text.
```

**Poor examples (avoid):**

```
Read everything and tell me about it.
```

---

## Content Sources ReadAgent Handles

| Content type | How it arrives in upstream |
|-------------|---------------------------|
| Web page body | From `search_agent` snippet or a fetch tool |
| File text | From a file-loading tool or direct injection |
| Previous agent output | From `search_agent`, `retrieve_agent`, etc. |
| Raw API response | From `tool` / `mcp` task results |

`ReadAgent` does **not** fetch URLs itself — the content must already be in `upstream`.

---

## Output Contract

`ReadAgent` returns an `AgentResult`:

```python
ok(self.name, task_id, TaskType.read, result)   # extracted text string
fail(self.name, task_id, TaskType.read, str(e)) # on LLM error
```

Output is a **plain text string** — structured enough for downstream agents to parse, but not a typed schema object (unlike `AnalyzeAgent` which uses `AnalysisOutput`).

---

## Chaining Pattern

For long documents, chain `read` → `summarize` to avoid context overflow:

```json
[
  {
    "task_id": "r1",
    "task_type": "read",
    "instruction": "Extract all benchmark results and model names from the document",
    "dependent_task_ids": ["fetch_1"]
  },
  {
    "task_id": "sum1",
    "task_type": "summarize",
    "instruction": "Summarise the extracted benchmark data into a compact overview",
    "dependent_task_ids": ["r1"]
  }
]
```

---

## Quality Principles

1. **Instruction-scoped extraction** — extract only what the instruction asks for
2. **Preserve verbatim data** — numbers, dates, proper nouns must not be paraphrased
3. **Signal over noise** — strip boilerplate, navigation, ads, repeated headers
4. **No inference** — if the content does not contain the requested information, state that explicitly
5. **Single responsibility** — one `read` task extracts one category of information

---

## Related

- [agents/read_agent.py](../agents/read_agent.py) — implementation
- [agents/search_agent.py](../agents/search_agent.py) — often produces upstream content
- [agents/retrieve_agent.py](../agents/retrieve_agent.py) — alternative upstream source
- [agents/summarize_agent.py](../agents/summarize_agent.py) — common downstream consumer
- [plan/task.py](../plan/task.py) — `TaskType.read`
