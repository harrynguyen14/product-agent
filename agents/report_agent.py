from __future__ import annotations

from typing import Any

from actions.action import LLMAction
from actions.action_node import ActionNode
from agents.base import BaseAgent
from plan.task import TaskType
from schemas.agent_result import AgentResult, AgentSuccess, fail, ok
from schemas.report import ReportOutput

_BASE_SYSTEM = (
    "Bạn là chuyên gia viết báo cáo nghiên cứu. "
    "Viết báo cáo có cấu trúc, chất lượng nghiên cứu cao, chỉ dùng thông tin có trong input. "
    "QUAN TRỌNG: Toàn bộ báo cáo — tất cả các section, heading, bullet, và nội dung văn xuôi — "
    "PHẢI viết bằng tiếng Việt. Giữ nguyên các thuật ngữ kỹ thuật tiếng Anh "
    "(ví dụ: 'vector database', 'token', 'embedding', 'retrieval') nhưng toàn bộ văn bản xung quanh phải là tiếng Việt."
)

PROMPT = """\
## Mục tiêu nghiên cứu
{goal}

## Dữ liệu đã tổng hợp
{upstream}

## Nguồn dữ liệu (upstream tasks)
{source_list}

---

Viết một báo cáo nghiên cứu đầy đủ bằng tiếng Việt với các yêu cầu sau:

### Yêu cầu nội dung
1. **executive_summary**: 2–3 câu tóm tắt toàn bộ nghiên cứu.
2. **main_conclusion**: 1 câu kết luận chính dựa trên dữ liệu.
3. **final_recommendation**: Khuyến nghị hành động cụ thể, có thể thực hiện ngay.
4. **findings_table**: Danh sách phát hiện dạng structured, mỗi item có:
   - `finding`: tên phát hiện ngắn gọn
   - `detail`: giải thích chi tiết 1–2 câu
   - `source`: tag nguồn dạng [search_1] hoặc [analyze_1]
5. **analysis**: Đoạn văn phân tích xu hướng, pattern, điểm bất thường — tối thiểu 3 câu.
6. **knowledge_gaps**: Những gì dữ liệu không trả lời được — liệt kê cụ thể.
7. **risks**: Rủi ro kỹ thuật hoặc kinh doanh liên quan — cụ thể, không chung chung.
8. **recommendations**: Chi tiết hơn final_recommendation — các bước hành động ưu tiên.
9. **sources**: Danh sách nguồn dạng ["[1] Tên nguồn — URL hoặc task_id", ...].
10. **methodology**: Mô tả ngắn cách dữ liệu được thu thập (search queries, tools, số kết quả).
11. **telegram_summary**: 2–3 câu TÓM TẮT NGẮN GỌN để gửi qua Telegram — viết như thông báo tin tức.
12. **key_facts**: 3–5 sự kiện/số liệu cụ thể nhất từ dữ liệu — dạng bullet facts.

### Yêu cầu bắt buộc
- Toàn bộ nội dung phải bằng tiếng Việt.
- Mỗi claim trong findings_table PHẢI có source tag tương ứng với upstream task.
- Chỉ dùng thông tin có trong phần "Dữ liệu đã tổng hợp" — không bịa thêm.
- Nếu dữ liệu không đủ cho một mục, ghi "Cần thêm dữ liệu" thay vì bịa.
- `telegram_summary` phải ngắn gọn, dễ đọc trên điện thoại (tối đa 3 câu).
"""


def _compute_confidence(upstream: dict[str, Any]) -> float:
    """Tính confidence_score dựa trên tỷ lệ upstream tasks có nội dung thực.

    Logic:
    - Mỗi upstream AgentSuccess có nội dung không rỗng → +1 điểm
    - Mỗi upstream AgentFailure hoặc rỗng → +0 điểm
    - Score = số task có data / tổng số task upstream
    - Tối đa 0.9 (không bao giờ 100% vì luôn có uncertainty)
    """
    if not upstream:
        return 0.0

    total = len(upstream)
    has_data = 0
    for v in upstream.values():
        if v is None:
            continue
        v_str = str(v).strip()
        if v_str and v_str not in ("None", "", "(no data)", "(no upstream data)"):
            has_data += 1

    raw = has_data / total if total > 0 else 0.0
    return round(min(raw * 0.9, 0.9), 2)  # cap at 0.9


class ReportAgent(BaseAgent):
    skill_file: str = "writing_skill.md"
    goal: str = ""

    async def run(self, task: dict, upstream: dict[str, Any]) -> AgentResult:
        task_id = task.get("task_id", "")

        if not upstream:
            return fail(
                self.name, task_id, TaskType.report,
                "No upstream data available for report. "
                "Ensure search/analyze/synthesize tasks ran successfully.",
            )

        upstream_str = (
            "\n\n---\n\n".join(f"[{k}]:\n{v}" for k, v in upstream.items())
            if upstream else "(no data)"
        )

        non_empty = [v for v in upstream.values() if v and str(v).strip() not in ("", "None")]
        if not non_empty:
            return fail(
                self.name, task_id, TaskType.report,
                "All upstream tasks produced empty output. Cannot generate a meaningful report.",
            )

        # Build source list for prompt — shows LLM which task IDs to cite
        source_list = "\n".join(f"- [{k}]: {str(v)[:80]}..." for k, v in upstream.items())

        # Compute confidence from upstream completeness BEFORE calling LLM
        auto_confidence = _compute_confidence(upstream)

        action = self._make_action(LLMAction)
        node = ActionNode(name=self.name, schema_cls=ReportOutput)
        node.set_action(action)

        try:
            result: ReportOutput = await node.run(
                PROMPT.format(
                    goal=self.goal or task.get("instruction", ""),
                    upstream=upstream_str,
                    source_list=source_list,
                ),
                system_msg=self._get_system(_BASE_SYSTEM),
            )
            # Override LLM-assigned confidence with computed value
            object.__setattr__(result, "confidence_score", auto_confidence)
            return ok(self.name, task_id, TaskType.report, result)
        except Exception as e:
            return fail(self.name, task_id, TaskType.report, str(e))
