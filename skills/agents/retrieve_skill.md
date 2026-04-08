# retrieve_skill — Vector Store and Database Retrieval

## Purpose

Guide `RetrieveAgent` to fetch relevant documents or records from a vector store or database using semantic similarity or a custom retrieval function. Returns ranked document chunks ready for downstream agents to process.

---

## When to Use

| Situation | Use this skill |
|-----------|---------------|
| Data is already indexed in a vector store | Yes |
| Need semantically similar documents to a query | Yes |
| Need to search the live web | No — use `search_agent` |
| Need to read a specific known file or URL | No — use `read_agent` |
| No retrieval function is configured | Falls back to LLM-based retrieval |

---

## Position in Pipeline

```
[pre-indexed knowledge base / vector store]
        ↓
   retrieve_agent  ← this skill
        ↓
   read_agent (optional — to extract specific info)
        ↓
   summarize_agent / analyze_agent
        ↓
   synthesize / report / writing_skill
```

---

## How RetrieveAgent Works

`RetrieveAgent` has two operating modes depending on whether a `retrieve_fn` is injected:

### Mode 1 — Custom retrieval function (preferred)

```python
# retrieve_agent.py — retrieve_fn path
docs = self.retrieve_fn(instruction, 8)   # top-8 results
output = "\n\n".join(
    f"[{i+1}] (score={d['score']:.2f}) {d['content']}"
    for i, d in enumerate(docs)
)
```

Output format:
```
[1] (score=0.92) <document chunk text>
[2] (score=0.87) <document chunk text>
...
[8] (score=0.61) <document chunk text>
```

### Mode 2 — LLM fallback (no retrieve_fn configured)

`RetrieveAgent` delegates to the LLM with the upstream context, asking it to "retrieve" relevant information conceptually. **This mode does not query a real database.**

---

## Registering a Retrieval Function

`retrieve_fn` is injected at registry build time in [agents/registry.py](../agents/registry.py):

```python
registry.register(
    TaskType.retrieve,
    RetrieveAgent(retrieve_fn=my_retrieve_fn).set_llm(llm)
)
```

The function signature:
```python
def retrieve_fn(query: str, top_k: int) -> list[dict]:
    # Returns list of {"content": str, "score": float, ...}
    ...
```

---

## Recommended Instruction Patterns

```
Retrieve documents about: [SPECIFIC TOPIC OR QUESTION]
Focus on: [aspect if applicable]
```

**Good examples:**

```
Retrieve documents about PostgreSQL indexing strategies for time-series data.
```

```
Retrieve the most relevant sections about authentication middleware from the codebase docs.
```

---

## Output Contract

```python
ok(self.name, task_id, TaskType.retrieve, output)   # ranked chunks as string
fail(self.name, task_id, TaskType.retrieve, str(e)) # on error
```

Output is a formatted string of ranked document chunks — direct input for `read_agent` or `summarize_agent`.

---

## Combining with Other Agents

`retrieve_agent` and `search_agent` are complementary:

| | `retrieve_agent` | `search_agent` |
|-|-----------------|---------------|
| Data source | Pre-indexed vector store / DB | Live web (SerpAPI) |
| Result type | Ranked chunks with scores | Titles, URLs, snippets |
| Latency | Low (local) | Higher (network) |
| Coverage | Limited to indexed data | Open web |
| Freshness | Depends on index update | Real-time |

For maximum coverage, run both in parallel:

```json
[
  {"task_id": "r1", "task_type": "retrieve", "dependent_task_ids": [], ...},
  {"task_id": "s1", "task_type": "search",   "dependent_task_ids": [], ...},
  {
    "task_id": "synth",
    "task_type": "synthesize",
    "instruction": "Merge retrieved docs and web search results into a unified overview",
    "dependent_task_ids": ["r1", "s1"]
  }
]
```

---

## Quality Principles

1. **Score threshold awareness** — results with score < 0.5 are likely irrelevant; downstream agents should deprioritise them
2. **Top-k default = 8** — balances recall and context size; reduce for very large chunks
3. **Query matches instruction** — the retrieval query should be the full task instruction, not a keyword
4. **Fallback is not retrieval** — LLM fallback mode produces synthesised text, not real document retrieval; label it as such
5. **Do not chunk yourself** — pass raw retrieved chunks downstream; let `read_agent` or `summarize_agent` filter

---

## Related

- [agents/retrieve_agent.py](../agents/retrieve_agent.py) — implementation
- [agents/registry.py](../agents/registry.py) — where `retrieve_fn` is injected
- [agents/search_agent.py](../agents/search_agent.py) — complementary live web retrieval
- [agents/read_agent.py](../agents/read_agent.py) — processes retrieved chunks
- [agents/summarize_agent.py](../agents/summarize_agent.py) — common downstream consumer
- [plan/task.py](../plan/task.py) — `TaskType.retrieve`
