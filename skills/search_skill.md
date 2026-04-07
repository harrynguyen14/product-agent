# search_skill — Targeted Information Retrieval

## Purpose

Guide `SearchAgent` to select the right tool, build effective queries, and return clean results that downstream agents (`summarize`, `analyze`) can consume immediately. This skill focuses on **input quality** — garbage in, garbage out.

---

## When to Use

| Situation | Use this skill |
|-----------|---------------|
| Need real-time data from the web (news, prices, events) | Yes — use `web_search_tool` |
| Data already exists in vector store / database | No — use `retrieve_agent` |
| Need to read content from a specific URL or file | No — use `read_agent` |
| Query is too broad, needs breaking down first | No — run `decompose_agent` first |
| Need multiple angles in parallel | Yes — spawn multiple independent search tasks |

---

## Position in Pipeline

```
goal / decompose_agent
        ↓
   search_agent  ← this skill
     (web_search_tool via SerpAPI)
        ↓
   summarize_agent / retrieve_agent
        ↓
   analyze / synthesize / writing_skill
```

---

## How SearchAgent Selects a Tool

`SearchAgent` receives a tool list from `ToolRegistry`, selects via LLM, then calls that tool.  
Default registered tool: **`web_search`** (SerpAPI / Google).

```
# tools/web_search.py — output format
[1] Title
    URL: https://...
    Snippet text...

[2] Title
    ...
```

**Query patterns by question type:**

| Question type | Recommended query pattern |
|--------------|--------------------------|
| Recent events | `"<topic> 2025 OR 2026"` |
| Product / tech comparison | `"<A> vs <B> comparison"` |
| Data / statistics | `"<topic> statistics data report"` |
| Technical guides | `"<topic> tutorial guide best practices"` |
| News | `"<topic> news latest"` |

---

## Recommended Task Instruction Format

When `DecomposeAgent` or `WritePlan` creates a `search` task, the instruction should follow this pattern:

```
Search: [SPECIFIC TOPIC]
Scope: [time range / source / language if applicable]
Need to know: [specific question to answer]
```

**Good example:**
```
Search AI coding tools market share Q1 2026 (Claude Code, Cursor, Copilot).
Need to know: user count, revenue, growth rate.
```

**Poor example (avoid):**
```
Look into AI tools.
```

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `SERPAPI_API_KEY not set` | Missing env var | Check `.env`, set `SERPAPI_API_KEY` |
| `Tool 'X' not found` | LLM called wrong tool name | `SearchAgent` auto-returns `fail()` with raw output |
| `No results found` | Query too narrow | Broaden query, remove filters |
| Irrelevant results | Query too broad | Add more specific keywords |
| Timeout | SerpAPI slow | httpx default timeout is 30s — increase if needed |

`SearchAgent` always returns a consistent `AgentResult` as `ok()` or `fail()`.

---

## Multi-Round Search Strategy

When a question requires multiple perspectives, `DecomposeAgent` should create **multiple parallel search tasks** instead of one broad task:

```json
[
  {
    "task_id": "s1",
    "task_type": "search",
    "instruction": "Search AI coding tools market share 2025-2026",
    "dependent_task_ids": []
  },
  {
    "task_id": "s2",
    "task_type": "search",
    "instruction": "Search pricing models and revenue of Cursor, GitHub Copilot",
    "dependent_task_ids": []
  },
  {
    "task_id": "sum1",
    "task_type": "summarize",
    "instruction": "Synthesize search results into a market overview summary",
    "dependent_task_ids": ["s1", "s2"]
  }
]
```

`ActionGraph` runs `s1` and `s2` in parallel, then merges both outputs into `sum1`.

---

## Standard Output Format from web_search_tool

```
[1] <Title>
    URL: <url>
    <snippet 1-3 sentences>

[2] <Title>
    URL: <url>
    <snippet>
...
```

The downstream agent (`SummarizeAgent`) receives this block via the `upstream` dict, keyed by `search_agent`.

---

## Quality Principles

1. **One task = one clear query** — do not bundle multiple questions into one search task
2. **Prioritize recency** — add the year to queries when current data is needed
3. **No fabrication** — if nothing is found, return `fail()`, never guess
4. **Default result count = 5** — enough to summarize, won't overwhelm context
5. **Tool selection is the LLM's responsibility** — `SearchAgent` does not hard-code tool names

---

## Examples

### Example 1 — Research topic (good)

**Instruction:**
```
Search: AI agent memory architectures 2024-2025
Scope: academic papers, technical blogs, framework documentation
Need to know: types of memory (short-term, long-term, episodic, semantic), representative frameworks (MemGPT, LangMem, Letta), trade-offs
```

**Queries issued (in order):**
```
Thought: The goal requires information about memory types and frameworks. I'll start with a broad query then narrow down.
Action: web_search(AI agent memory architecture short-term long-term episodic 2025)
Observation: [results about MemGPT, episodic memory, vector stores...]

Thought: Results mention MemGPT and LangMem. I need specifics on their design trade-offs.
Action: web_search(MemGPT LangMem Letta agent memory framework comparison 2025)
Observation: [results comparing the frameworks...]

Final Answer: Tìm thấy 2 nhóm kiến trúc chính:
1. In-context memory (short-term): toàn bộ history trong context window — đơn giản nhưng tốn token.
2. External memory (long-term): vector DB (Chroma, Pinecone) + retrieval — scale tốt hơn.
Framework nổi bật: MemGPT (hierarchical paging), LangMem (semantic compression), Letta (stateful agents).
```

---

### Example 2 — Comparison query (good)

**Instruction:**
```
Search: Vector database vs knowledge graph for agent memory storage
Scope: engineering blogs and benchmarks, 2024-2026
Need to know: latency, query flexibility, setup complexity, best use-case fit
```

**Queries issued:**
```
Thought: Need to compare two storage paradigms. Start with direct comparison.
Action: web_search(vector database vs knowledge graph agent memory storage comparison 2025)
Observation: [results...]

Thought: Results are general. Need benchmark data on latency and query types.
Action: web_search(Pinecone Neo4j latency benchmark agent retrieval 2025)
Observation: [results...]

Final Answer: Vector DB (Pinecone, Chroma): latency ~5-20ms, tốt cho similarity search, setup đơn giản.
Knowledge Graph (Neo4j): latency ~10-50ms, tốt cho relational queries, setup phức tạp hơn.
Kết luận: Dùng vector DB cho semantic recall; graph cho multi-hop reasoning.
```

---

### Example 3 — Too vague (bad — will trigger retry)

**Instruction:**
```
Tìm kiếm về memory cho agent
```

**Problem:** Không có Scope, không có Need to know, quá ngắn (< 40 ký tự).
**Result:** `PlanValidator` reject plan, yêu cầu WritePlan sửa lại instruction.

---

## Related

- [agents/search_agent.py](../agents/search_agent.py) — implementation
- [tools/web_search.py](../tools/web_search.py) — SerpAPI wrapper
- [agents/decompose_agent.py](../agents/decompose_agent.py) — produces search tasks
- [agents/summarize_agent.py](../agents/summarize_agent.py) — consumes output
- [agents/retrieve_agent.py](../agents/retrieve_agent.py) — alternative when data is already available
- [plan/task.py](../plan/task.py) — `TaskType.search`
