---
name: writing-report
description: Structured report writer. Use when formatting summarized or analyzed data into a final detailed table report ready to present to the user, send via Telegram, or save to file. Does not generate new information — only restructures upstream output.
---

# writing_skill — Structured Report from Summarize Output

## Purpose

Receive output from `SummarizeAgent` (and optionally `AnalyzeAgent` / `SynthesizeAgent`) and reformat it into a **detailed, structured table report** ready to present to the user, send via Telegram, or save to file.

No new information is generated. This skill only restructures and clearly presents what was synthesised upstream.

> **Language rule:** All skill logic and prompts are written in English. The **final report output delivered to the user must be in Vietnamese**.

---

## When to Use

| Situation | Use this skill |
|-----------|---------------|
| After `summarize` → need a table-format report | Yes |
| After `analyze` or `synthesize` → need detailed presentation | Yes |
| After `report` → `ReportOutput` already complete | **No** — `ReportAgent` is sufficient |
| Need a short Telegram summary | Use `telegram_summary` field in `ReportOutput` |

---

## Position in Pipeline

```
read / search / retrieve
        ↓
   summarize_agent        ← primary input source
        ↓
  [analyze / synthesize]  ← optional, for deeper processing
        ↓
   writing_skill          ← this skill — formats into table report
        ↓
   validate_agent         ← quality check before delivery
```

---

## Output Report Format (Vietnamese)

The writing skill produces a Markdown report with the following standard structure:

```markdown
# [TIÊU ĐỀ BÁO CÁO]

**Ngày:** YYYY-MM-DD  
**Nguồn dữ liệu:** [task name / upstream agents]  
**Độ tin cậy:** [cao / trung bình / thấp — based on input quality]

---

## Tóm tắt điều hành

[2–3 sentences capturing the full content]

---

## Kết quả chính

| # | Phát hiện | Chi tiết | Nguồn / Căn cứ |
|---|-----------|----------|----------------|
| 1 | ...       | ...      | ...            |
| 2 | ...       | ...      | ...            |
| N | ...       | ...      | ...            |

---

## Phân tích & Nhận xét

| Chiều cạnh | Nội dung |
|------------|----------|
| Xu hướng nổi bật | ... |
| Mối liên hệ / Pattern | ... |
| Điểm bất thường | ... |
| Hạn chế của dữ liệu | ... |

---

## Rủi ro & Khoảng trống kiến thức

| Loại | Mô tả | Mức độ |
|------|-------|--------|
| Thiếu dữ liệu | ... | Cao / Trung / Thấp |
| Mâu thuẫn | ... | ... |
| Giả định chưa kiểm chứng | ... | ... |

---

## Khuyến nghị

| Ưu tiên | Hành động | Lý do |
|---------|-----------|-------|
| 1 | ... | ... |
| 2 | ... | ... |

---

## Metadata

| Trường | Giá trị |
|--------|---------|
| Task ID | ... |
| Agents upstream | summarize_agent [, analyze_agent, synthesize_agent] |
| Tổng số nguồn | N |
| Confidence score | 0.0 – 1.0 |
```

---

## Agent Prompt Template

When implementing `WritingAgent` or invoking this skill from the task pipeline, use the following prompt:

```
## Task
Rewrite the information below as a detailed table report following the standard format.

## Mandatory Rules
- Use only facts present in the Input section — do not invent anything
- Every finding in the table MUST be traceable back to the input
- If data is missing, write "N/A" or add an entry under "Khoảng trống kiến thức"
- Output language: Vietnamese (keep English technical terms as-is)
- Format: Markdown with tables — avoid long bullet lists

## Input (output from summarize_agent)
{upstream}

## Required Output Structure
Use the standard 5-section table report:
1. Tóm tắt điều hành
2. Kết quả chính (table)
3. Phân tích & Nhận xét (table)
4. Rủi ro & Khoảng trống (table)
5. Khuyến nghị (table)
```

---

## Mapping to ReportOutput Schema

`writing_skill` maps directly to `ReportOutput` ([schemas/report.py](../schemas/report.py)):

| Report section | ReportOutput field |
|---------------|-------------------|
| Tóm tắt điều hành | `executive_summary` |
| Kết quả chính (table) | `key_findings` + `key_facts` |
| Phân tích & Nhận xét | `analysis` |
| Khoảng trống kiến thức | `knowledge_gaps` |
| Rủi ro | `risks` |
| Khuyến nghị | `recommendations` |
| Confidence score | `confidence_score` |
| Telegram summary | `telegram_summary` |

---

## Quality Principles

Adapted from MetaGPT `CONDUCT_RESEARCH_PROMPT` and project coding standards:

1. **Grounded only** — every table cell must be traceable to the original input
2. **Tables over bullet lists** — comparative or enumerated data always uses tables
3. **Concise and structured** — each cell is max 2 sentences; avoid prose paragraphs inside tables
4. **Explicit confidence** — always state the reliability level based on source quality
5. **No inference** — if input is insufficient, write "Cần thêm dữ liệu" rather than guessing

---

## Examples

### Example 1 — Research report (good output)

**Input (from synthesize_agent):**
```
unified_result: "MemGPT dùng hierarchical paging để quản lý in-context vs external memory.
LangMem dùng semantic compression. Letta là stateful agent framework build trên MemGPT."
consensus_points: ["Vector DB phù hợp cho similarity recall", "Knowledge graph tốt hơn cho multi-hop"]
contradictions: ["Source A: latency vector DB ~5ms; Source B: ~20ms — khác nhau do benchmark environment"]
uncertainties: ["Chưa có benchmark production scale cho Letta"]
```

**Expected output (Vietnamese):**

```markdown
## Tóm tắt điều hành

Nghiên cứu xác định ba framework memory agent nổi bật: MemGPT, LangMem, và Letta,
mỗi framework áp dụng chiến lược khác nhau để cân bằng giữa chi phí token và khả năng recall.
Vector database phù hợp cho similarity search; knowledge graph phù hợp cho multi-hop reasoning.

## Kết quả chính

| # | Phát hiện | Chi tiết | Nguồn |
|---|-----------|----------|-------|
| 1 | MemGPT dùng hierarchical paging | Phân chia in-context và external memory | Source [synth] |
| 2 | LangMem dùng semantic compression | Nén history để giảm token | Source [synth] |
| 3 | Vector DB latency ~5-20ms | Phù hợp cho similarity recall | Source [a1], Source [a2] |

## Phân tích & Nhận xét

| Chiều cạnh | Nội dung |
|------------|----------|
| Xu hướng nổi bật | External memory (vector DB) đang là hướng chính |
| Mối liên hệ | MemGPT → Letta: evolution của stateful agent pattern |
| Điểm bất thường | Latency vector DB chênh lệch giữa các nguồn (5ms vs 20ms) |
| Hạn chế dữ liệu | Chưa có benchmark production scale cho Letta |

## Rủi ro & Khoảng trống kiến thức

| Loại | Mô tả | Mức độ |
|------|-------|--------|
| Mâu thuẫn | Latency vector DB: Source A 5ms vs Source B 20ms | Trung bình |
| Thiếu dữ liệu | Benchmark production scale Letta chưa có | Cao |

## Khuyến nghị

| Ưu tiên | Hành động | Lý do |
|---------|-----------|-------|
| 1 | Dùng vector DB (Chroma/Pinecone) cho short-term recall | Latency thấp, setup đơn giản |
| 2 | Benchmark Letta trên production workload | Chưa có dữ liệu thực tế |
```

---

### Example 2 — Empty upstream (bad — agent returns fail())

**Input:** `upstream = {}` hoặc toàn bộ upstream là AgentFailure

**Result:** `ReportAgent` trả về `fail()` với message:
```
"No upstream data available for report. Ensure search/analyze/synthesize tasks ran successfully."
```
Không bao giờ sinh ra báo cáo giả với nội dung "thiếu dữ liệu".

---

## Related

- [agents/summarize_agent.py](../agents/summarize_agent.py) — primary input source
- [agents/report_agent.py](../agents/report_agent.py) — agent using ReportOutput schema
- [schemas/report.py](../schemas/report.py) — standard output schema
- [agents/analyze_agent.py](../agents/analyze_agent.py) — optional upstream before writing
- [plan/task.py](../plan/task.py) — `TaskType.report` used for this task
