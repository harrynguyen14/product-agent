import re
from datetime import datetime
from pathlib import Path
from typing import Any

_MAX_LEN = 4000


def _truncate(text: str, max_len: int = _MAX_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 40] + "\n\n<i>... [xem file đính kèm để đọc đầy đủ]</i>"


def _escape(text: str) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── Progress labels ────────────────────────────────────────────────────────────

def format_thinking(node: str) -> str:
    labels = {
        "ClarifyAgent":    "🔍 Đang phân tích yêu cầu...",
        "PlanAgent":       "🗺 Đang lập kế hoạch nghiên cứu...",
        "AdminAgent":      "🧠 Admin đang điều phối...",
        "RAGAgent":        "🗄 Đang truy vấn kho kiến thức...",
        "MCPAgent":        "🌐 Đang tìm kiếm web...",
        "SummaryAgent":    "🔬 Đang tổng hợp nghiên cứu...",
        "ValidationAgent": "✅ Đang kiểm tra kết quả...",
        "ReportAgent":     "📝 Đang viết báo cáo...",
        "AssignAgent":     "📌 Đang phân công nhiệm vụ...",
    }
    return labels.get(node, f"⚙ {node}...")


# ── Plan summary ───────────────────────────────────────────────────────────────

def format_plan(state: dict) -> str:
    plan = state.get("plan")
    if not plan:
        return ""
    # Plan._tasks is the authoritative list after refactor
    tasks = getattr(plan, "_tasks", None) or getattr(plan, "tasks", [])
    if not tasks:
        return ""
    lines = ["<b>📋 Kế hoạch nghiên cứu</b>"]
    for t in tasks:
        task_type = _escape(getattr(t, "task_type", ""))
        instruction = _escape(getattr(t, "instruction", ""))
        lines.append(f"• <code>[{task_type}]</code> {instruction}")
    return _truncate("\n".join(lines))


# ── Clarification ──────────────────────────────────────────────────────────────

def format_clarification_question(state: dict) -> str:
    q = _escape(state.get("clarification_question", ""))
    return f"❓ <b>Cần thêm thông tin:</b>\n\n{q}"


# ── Telegram summary — ngắn gọn, trọng tâm ────────────────────────────────────

def format_telegram_summary(state: dict) -> str:
    """
    Tóm tắt ngắn gọn từ telegram_summary của WritingOutput.
    Fallback: dùng main_conclusion + key_facts nếu telegram_summary rỗng.
    """
    report = state.get("report_output")
    if not report:
        return ""

    # ReportAgent trả về plain string
    if isinstance(report, str):
        return _truncate(_escape(report))

    # Ưu tiên telegram_summary (đã được LLM format 2-3 dòng)
    telegram_summary = _escape(getattr(report, "telegram_summary", ""))
    if telegram_summary:
        lines = [telegram_summary, "", "<i>📎 Xem file đính kèm để đọc báo cáo đầy đủ</i>"]
        return _truncate("\n".join(lines))

    # Fallback nếu telegram_summary rỗng
    conclusion = _escape(getattr(report, "main_conclusion", ""))
    recommendation = _escape(getattr(report, "final_recommendation", ""))
    key_facts = getattr(report, "key_facts", [])
    risks = getattr(report, "risks", [])

    lines = []
    if conclusion:
        lines += [f"<b>🔎 Kết luận</b>", conclusion, ""]
    if key_facts:
        lines.append("<b>📊 Dữ liệu chính</b>")
        for f in key_facts[:3]:
            lines.append(f"• {_escape(f)}")
        lines.append("")
    if recommendation:
        lines += [f"<b>✅ Khuyến nghị</b>", recommendation, ""]
    if risks:
        lines.append("<b>⚠️ Rủi ro</b>")
        for r in risks[:2]:
            lines.append(f"• {_escape(r)}")
        lines.append("")

    lines.append("<i>📎 Xem file đính kèm để đọc báo cáo đầy đủ</i>")
    return _truncate("\n".join(lines))


# ── Assigned Tasks (Telegram) ─────────────────────────────────────────────────

def format_assigned_tasks(state: dict) -> str:
    assign = state.get("assign_output")
    if not assign:
        return ""
    tasks = getattr(assign, "tasks", [])
    if not tasks:
        return ""
    lines = [f"<b>📌 Nhiệm vụ R&D ({len(tasks)})</b>\n"]
    for i, t in enumerate(tasks, 1):
        title = _escape(getattr(t, "title", ""))
        owner = _escape(getattr(t, "owner_role", ""))
        priority = getattr(t, "priority", "medium")
        if hasattr(priority, "value"):
            priority = priority.value
        p_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
        lines.append(f"{i}. {p_icon} <b>{title}</b> — <i>{owner}</i>")
    return _truncate("\n".join(lines))


# ── Error ─────────────────────────────────────────────────────────────────────

def format_error(error: Any) -> str:
    return f"❌ <b>Lỗi pipeline</b>\n\n<code>{_escape(str(error)[:500])}</code>"


# ── Export 1: Workflow Trace ──────────────────────────────────────────────────

def export_workflow_trace(state: dict, output_dir: str = "./reports") -> Path | None:
    """
    Xuất file workflow trace — ghi lại từng agent đã làm gì, suy luận ra sao.
    """
    trace_entries = state.get("workflow_trace", [])
    problem = state.get("user_problem", "")
    plan = state.get("plan")

    if not trace_entries and not plan:
        return None

    lines = [
        f"# Workflow Trace — Báo cáo quá trình nghiên cứu",
        f"",
        f"> **Câu hỏi:** {problem}",
        f"> **Thời gian:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"",
        f"---",
        f"",
    ]

    # Plan overview
    if plan:
        tasks = getattr(plan, "tasks", [])
        lines += [
            f"## Kế hoạch thực thi",
            f"",
            f"**Mục tiêu:** {getattr(plan, 'goal', '')}",
            f"",
            f"| Task | Type | Priority | Instruction |",
            f"|------|------|----------|-------------|",
        ]
        for t in tasks:
            lines.append(
                f"| {t.id} | {t.task_type} | {t.priority} | {t.instruction[:80]} |"
            )
        lines += ["", "---", ""]

    # Agent trace
    lines += [f"## Quá trình thực thi từng Agent", f""]

    for i, entry in enumerate(trace_entries, 1):
        ts = entry.get("timestamp", "")
        agent = entry.get("agent", "")
        task = entry.get("task", "")
        reasoning = entry.get("reasoning", "")
        output = entry.get("output_summary", "")

        lines += [
            f"### {i}. {agent} `[{ts}]`",
            f"",
        ]
        if task:
            lines += [f"**Task:** {task}", f""]
        lines += [
            f"**Suy luận:**",
            f"{reasoning}",
            f"",
            f"**Kết quả:**",
            f"{output}",
            f"",
            f"---",
            f"",
        ]

    # Admin summary
    admin = state.get("admin_output")
    if admin:
        decision = getattr(admin, "decision", "")
        if hasattr(decision, "value"):
            decision = decision.value
        lines += [
            f"## Tổng kết Admin",
            f"",
            f"- **Quyết định:** {decision}",
            f"- **Confidence:** {admin.confidence_score:.0%}",
            f"- **Coverage:** {admin.coverage_score:.0%}",
            f"- **Executive Summary:** {admin.executive_summary}",
            f"",
            f"**Key Facts:**",
        ]
        for f in getattr(admin, "key_facts", []):
            lines.append(f"- {f}")
        lines += ["", "**Knowledge Gaps:**"]
        for g in getattr(admin, "knowledge_gaps", []):
            lines.append(f"- {g}")
        lines.append("")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w\s\-]", "", problem).strip()
    safe = re.sub(r"\s+", "_", safe)[:50]
    path = out_dir / f"{ts_str}_workflow_{safe}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ── Export 2: Structured Report ───────────────────────────────────────────────

def export_report_markdown(state: dict, output_dir: str = "./reports") -> Path | None:
    """
    Xuất báo cáo nghiên cứu từ WritingOutput (schema mới).
    Nếu report có workflow_markdown thì dùng luôn, không tự build lại.
    """
    report = state.get("report_output")
    if not report:
        return None

    # ReportAgent trả về plain string
    if isinstance(report, str):
        problem = state.get("user_problem", "")
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r"[^\w\s\-]", "", problem).strip()
        safe = re.sub(r"\s+", "_", safe)[:60]
        path = out_dir / f"{ts_str}_report_{safe}.md"
        header = (
            f"# Báo cáo Nghiên cứu\n\n"
            f"> **Câu hỏi:** {problem}\n"
            f"> **Ngày tạo:** {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
            f"---\n\n"
        )
        path.write_text(header + report, encoding="utf-8")
        return path

    problem = state.get("user_problem", "")
    assign = state.get("assign_output")
    tasks = getattr(assign, "tasks", []) if assign else []
    admin = state.get("admin_output")

    _title = getattr(report, "title", None)
    title = _title if isinstance(_title, str) else "Báo cáo Nghiên cứu"
    confidence = getattr(report, "confidence_score", 0)

    def _s(field, default=""):
        return getattr(report, field, default) or default

    def _lst(field):
        return getattr(report, field, []) or []

    lines = [
        f"# {title}",
        f"",
        f"> **Câu hỏi nghiên cứu:** {problem}",
        f"> **Ngày tạo:** {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        f"> **Độ tin cậy:** {confidence:.0%}",
        f"",
        f"---",
        f"",

        # 1. Executive Summary
        f"## 1. Tóm tắt điều hành",
        f"",
        _s("executive_summary"),
        f"",
        f"- **Kết luận chính:** {_s('main_conclusion')}",
        f"- **Khuyến nghị:** {_s('final_recommendation')}",
        f"",
        f"---",
        f"",

        # 2. Findings table
        f"## 2. Kết quả chính",
        f"",
    ]

    findings_table = _lst("findings_table")
    if findings_table and isinstance(findings_table[0], dict):
        lines += [
            f"| # | Phát hiện | Chi tiết | Nguồn |",
            f"|---|-----------|----------|-------|",
        ]
        for i, row in enumerate(findings_table, 1):
            finding = row.get("finding", "")
            detail = row.get("detail", "")
            source = row.get("source", "")
            lines.append(f"| {i} | {finding} | {detail} | {source} |")
    else:
        # Fallback to flat findings list
        flat = _lst("findings") or _lst("key_findings")
        for i, finding in enumerate(flat, 1):
            lines.append(f"**{i}.** {finding}")
            lines.append(f"")

    lines += [f"", f"---", f""]

    # 3. Key facts
    key_facts = _lst("key_facts")
    if key_facts:
        lines += [f"## 3. Dữ liệu & Sự kiện chính", f""]
        for fact in key_facts:
            lines.append(f"- {fact}")
        lines += [f"", f"---", f""]

    # 4. Analysis
    analysis = _s("analysis")
    if analysis:
        lines += [
            f"## 4. Phân tích & Nhận xét",
            f"",
            analysis,
            f"",
            f"---",
            f"",
        ]

    # 5. Risks
    risks = _lst("risks")
    if risks:
        lines += [f"## 5. Rủi ro & Hạn chế", f""]
        for r in risks:
            lines.append(f"- {r}")
        lines += [f"", f"---", f""]

    # 6. Knowledge Gaps
    lines += [f"## 6. Khoảng trống tri thức", f""]
    all_gaps = _lst("knowledge_gaps")
    if not all_gaps and admin:
        all_gaps = getattr(admin, "knowledge_gaps", [])
    for g in all_gaps:
        lines.append(f"- {g}")
    lines += [f"", f"---", f""]

    # 7. Recommendations
    recs = _s("recommendations")
    if recs:
        lines += [f"## 7. Khuyến nghị chi tiết", f"", recs, f"", f"---", f""]

    # 8. Methodology
    methodology = _s("methodology")
    if methodology:
        lines += [f"## 8. Phương pháp thu thập dữ liệu", f"", methodology, f"", f"---", f""]

    # 9. Sources
    sources = _lst("sources")
    if sources:
        lines += [f"## 9. Nguồn tham khảo", f""]
        for src in sources:
            lines.append(f"- {src}")
        lines += [f"", f"---", f""]

    # 10. Further Research
    further = _lst("further_research")
    if further:
        lines += [f"## 10. Hướng nghiên cứu tiếp theo", f""]
        for fr in further:
            lines.append(f"- {fr}")
        lines += [f"", f"---", f""]

    # 11. Action Plan (from AssignTaskAgent if available)
    if tasks:
        lines += [
            f"## 11. Action Plan",
            f"",
            f"| Nhiệm vụ | Phụ trách | Ưu tiên |",
            f"|----------|-----------|---------|",
        ]
        for t in tasks:
            priority = getattr(t, "priority", "medium")
            if hasattr(priority, "value"):
                priority = priority.value
            lines.append(
                f"| {getattr(t,'title','')} | {getattr(t,'owner_role','')} | {priority} |"
            )
        lines += [f"", f"---", f""]

    # Write
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w\s\-]", "", title).strip()
    safe = re.sub(r"\s+", "_", safe)[:60]
    path = out_dir / f"{ts_str}_report_{safe}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ── Helpers ───────────────────────────────────────────────────────────────────

def split_long_message(text: str, max_len: int = _MAX_LEN) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return parts
