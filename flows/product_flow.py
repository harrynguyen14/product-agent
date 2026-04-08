from __future__ import annotations

"""ProductFlow — PM-orchestrated full product development flow.

Flow:
    Phase 1 — Business Analysis
        PM assigns → BA analyzes → PM reviews (max 2 retries)

    Phase 2 — UI/UX Design
        PM assigns → UIUXDesigner designs → PM reviews vs BA output (max 2 retries)

    Phase 3 — Development (via ProjectDeveloper)
        PM assigns → ProjectDeveloper orchestrates:
            Arch → (Security + DevOps parallel) → (FE + BE parallel) → Tester
        PD reports back → PM reviews (max 2 retries)

    Phase 4 — Final Report
        PM assigns → BA writes final report → PM reviews → delivered to user
"""

import asyncio
from typing import AsyncGenerator, Optional

from infrastructure.logging import get_logger
from roles.product_manager import ProductManager
from roles.business_analyst import BusinessAnalyst
from roles.ui_ux_designer import UIUXDesigner
from roles.project_developer import ProjectDeveloper
from roles.software_architect import SoftwareArchitect
from roles.security_specialist import SecuritySpecialist
from roles.devops_engineer import DevOpsEngineer
from roles.frontend_dev import FrontendDev
from roles.backend_dev import BackendDev
from roles.tester import Tester
from roles.reporter import Reporter

logger = get_logger("product_flow")

MAX_RETRIES = 2  # max number of revision loops per phase


class ProductFlow:
    """Full product development flow orchestrated by PM.

    PM acts as the central coordinator: assigns work, reviews outputs,
    requests revisions when needed, and gates progression to next phase.

    Each phase yields streaming events so the Discord bot can relay
    messages in real-time with correct agent identities.
    """

    def __init__(
        self,
        pm: ProductManager,
        ba: BusinessAnalyst,
        designer: UIUXDesigner,
        pd: ProjectDeveloper,
        architect: Optional[SoftwareArchitect] = None,
        security: Optional[SecuritySpecialist] = None,
        devops: Optional[DevOpsEngineer] = None,
        fe_dev: Optional[FrontendDev] = None,
        be_dev: Optional[BackendDev] = None,
        tester: Optional[Tester] = None,
        reporter: Optional[Reporter] = None,
        compress_phases: bool = False,
    ) -> None:
        self._pm = pm
        self._ba = ba
        self._designer = designer
        self._pd = pd
        self._arch = architect
        self._security = security
        self._devops = devops
        self._fe = fe_dev
        self._be = be_dev
        self._tester = tester
        self._reporter = reporter or ba  # fallback: BA writes report
        self._compress_phases = compress_phases

    # ------------------------------------------------------------------
    # Public stream API
    # ------------------------------------------------------------------

    async def stream(
        self,
        requirement: str,
        plan_context: str = "",
    ) -> AsyncGenerator[dict, None]:
        """Stream all events from start to finish.

        Event types:
            role_start   — a role begins working
            role_done    — a role finished, output included
            pm_review    — PM evaluates an output (approved/revision)
            phase_start  — a new phase begins
            phase_done   — a phase completed
            flow_done    — entire flow finished
        """
        outputs: dict[str, str] = {}

        # ── Phase 1: Business Analysis ──────────────────────────────────
        async for event in self._phase_ba(requirement, plan_context, outputs):
            yield event

        ba_output = outputs.get("BusinessAnalyst", "")

        # Optionally compress BA output before passing to Phase 2 + 3
        ba_for_next = await self._compress("Business Analysis", ba_output) if self._compress_phases else ba_output

        # ── Phase 2: UI/UX Design ───────────────────────────────────────
        async for event in self._phase_uiux(requirement, ba_for_next, outputs):
            yield event

        uiux_output = outputs.get("UIUXDesigner", "")

        # Optionally compress UIUX output before passing to Phase 3
        uiux_for_next = await self._compress("UI/UX Design", uiux_output) if self._compress_phases else uiux_output

        # ── Phase 3: Development ────────────────────────────────────────
        async for event in self._phase_dev(requirement, ba_for_next, uiux_for_next, plan_context, outputs):
            yield event

        dev_summary = outputs.get("ProjectDeveloper_report", "")

        # ── Phase 4: Final Report ───────────────────────────────────────
        async for event in self._phase_report(requirement, outputs):
            yield event

        yield {
            "type": "flow_done",
            "flow": "product_flow",
            "outputs": outputs,
            "summary": outputs.get("FinalReport", dev_summary),
        }

    # ------------------------------------------------------------------
    # Phase 1 — Business Analysis
    # ------------------------------------------------------------------

    async def _phase_ba(
        self,
        requirement: str,
        plan_context: str,
        outputs: dict,
    ) -> AsyncGenerator[dict, None]:
        yield {"type": "phase_start", "phase": "1", "name": "Business Analysis"}

        # PM assigns BA
        yield {"type": "role_start", "role": "ProductManager"}
        pm_assign = await self._pm.run_task(
            f"## Yêu cầu từ user\n{requirement}\n\n"
            + (f"## Kế hoạch tổng thể\n{plan_context}\n\n" if plan_context else "")
            + "Hãy giao task cho BusinessAnalyst: nêu rõ yêu cầu phân tích nghiệp vụ, "
            "context cần thiết, và kỳ vọng output (User Stories, Acceptance Criteria, "
            "Business Rules, Out of Scope, Rủi ro, câu hỏi làm rõ nếu cần)."
        )
        yield {"type": "role_done", "role": "ProductManager", "output": pm_assign}

        # BA works — with revision loop
        ba_output = ""
        for attempt in range(MAX_RETRIES + 1):
            yield {"type": "role_start", "role": "BusinessAnalyst"}
            ba_prompt = (
                f"## Yêu cầu từ PM\n{pm_assign}\n\n"
                f"## Yêu cầu gốc của user\n{requirement}\n\n"
                + (f"## Kế hoạch tổng thể\n{plan_context}\n\n" if plan_context else "")
                + "Hãy phân tích nghiệp vụ và tạo functional specification đầy đủ."
            )
            if attempt > 0:
                ba_prompt += f"\n\n## Phản hồi từ PM (lần {attempt})\n{outputs.get('PM_feedback_ba', '')}\nHãy điều chỉnh theo phản hồi trên."

            ba_output = await self._ba.run_task(ba_prompt)
            outputs["BusinessAnalyst"] = ba_output
            yield {"type": "role_done", "role": "BusinessAnalyst", "output": ba_output}

            # PM reviews BA output
            yield {"type": "role_start", "role": "ProductManager"}
            pm_review = await self._pm.run_task(
                f"## BA vừa hoàn thành phân tích nghiệp vụ. Đây là output:\n{ba_output}\n\n"
                f"## Yêu cầu gốc của user\n{requirement}\n\n"
                "Hãy đánh giá: output có đầy đủ và phù hợp không? "
                "Nếu OK thì nói rõ 'CHẤP NHẬN'. "
                "Nếu cần sửa thì nói 'CẦN SỬA' và nêu cụ thể điểm cần điều chỉnh."
            )
            yield {"type": "pm_review", "role": "ProductManager", "target": "BusinessAnalyst",
                   "output": pm_review, "attempt": attempt + 1}

            if _pm_accepted(pm_review) or attempt >= MAX_RETRIES:
                break
            outputs["PM_feedback_ba"] = pm_review

        yield {"type": "phase_done", "phase": "1", "name": "Business Analysis"}

    # ------------------------------------------------------------------
    # Phase 2 — UI/UX Design
    # ------------------------------------------------------------------

    async def _phase_uiux(
        self,
        requirement: str,
        ba_output: str,
        outputs: dict,
    ) -> AsyncGenerator[dict, None]:
        yield {"type": "phase_start", "phase": "2", "name": "UI/UX Design"}

        # PM tags UIUXDesigner
        yield {"type": "role_start", "role": "ProductManager"}
        pm_assign = await self._pm.run_task(
            f"BA đã hoàn thành phân tích nghiệp vụ. Đây là kết quả:\n{ba_output}\n\n"
            "Hãy giao task cho UIUXDesigner: yêu cầu thiết kế UI/UX dựa trên BA spec trên. "
            "Cần: User Journey, wireframe layout, Design System (màu sắc, typography, components), UX Notes."
        )
        yield {"type": "role_done", "role": "ProductManager", "output": pm_assign}

        uiux_output = ""
        for attempt in range(MAX_RETRIES + 1):
            yield {"type": "role_start", "role": "UIUXDesigner"}
            uiux_prompt = (
                f"## Yêu cầu từ PM\n{pm_assign}\n\n"
                f"## Phân tích nghiệp vụ từ BA\n{ba_output}\n\n"
                "Hãy thiết kế UI/UX chi tiết: User Journey, wireframes (ASCII), Design System, UX Notes."
            )
            if attempt > 0:
                uiux_prompt += f"\n\n## Phản hồi từ PM (lần {attempt})\n{outputs.get('PM_feedback_uiux', '')}\nHãy điều chỉnh theo phản hồi trên."

            uiux_output = await self._designer.run_task(uiux_prompt)
            outputs["UIUXDesigner"] = uiux_output
            yield {"type": "role_done", "role": "UIUXDesigner", "output": uiux_output}

            # PM reviews — cross-checks with BA output
            yield {"type": "role_start", "role": "ProductManager"}
            pm_review = await self._pm.run_task(
                f"## UIUXDesigner vừa hoàn thành thiết kế. Đây là output:\n{uiux_output}\n\n"
                f"## BA spec để đối chiếu:\n{ba_output}\n\n"
                "Hãy đánh giá: design có phù hợp với BA spec không? "
                "Nếu OK thì nói 'CHẤP NHẬN'. "
                "Nếu cần sửa thì nói 'CẦN SỬA' và nêu cụ thể điểm cần điều chỉnh."
            )
            yield {"type": "pm_review", "role": "ProductManager", "target": "UIUXDesigner",
                   "output": pm_review, "attempt": attempt + 1}

            if _pm_accepted(pm_review) or attempt >= MAX_RETRIES:
                break
            outputs["PM_feedback_uiux"] = pm_review

        yield {"type": "phase_done", "phase": "2", "name": "UI/UX Design"}

    # ------------------------------------------------------------------
    # Phase 3 — Development (via ProjectDeveloper)
    # ------------------------------------------------------------------

    async def _phase_dev(
        self,
        requirement: str,
        ba_output: str,
        uiux_output: str,
        plan_context: str,
        outputs: dict,
    ) -> AsyncGenerator[dict, None]:
        yield {"type": "phase_start", "phase": "3", "name": "Development"}

        # PM assigns ProjectDeveloper
        yield {"type": "role_start", "role": "ProductManager"}
        pm_assign = await self._pm.run_task(
            f"BA và UIUXDesigner đã hoàn thành. Hãy giao toàn bộ task development cho ProjectDeveloper.\n\n"
            f"## BA Spec\n{ba_output}\n\n"
            f"## UI/UX Design\n{uiux_output}\n\n"
            f"## Yêu cầu gốc\n{requirement}\n\n"
            "Giao cho ProjectDeveloper: phân công Architect, Security, DevOps, FE, BE, Tester "
            "để xây dựng toàn bộ hệ thống."
        )
        yield {"type": "role_done", "role": "ProductManager", "output": pm_assign}

        pd_report = ""
        for attempt in range(MAX_RETRIES + 1):
            # PD announces its plan
            yield {"type": "role_start", "role": "ProjectDeveloper"}
            pd_plan = await self._pd.run_task(
                f"## Yêu cầu từ PM\n{pm_assign}\n\n"
                f"## BA Spec\n{ba_output}\n\n"
                f"## UI/UX Design\n{uiux_output}\n\n"
                "Trình bày kế hoạch phân công: ai làm gì, theo thứ tự nào."
                + (f"\n\n## Phản hồi PM lần trước\n{outputs.get('PM_feedback_dev', '')}" if attempt > 0 else "")
            )
            yield {"type": "role_done", "role": "ProjectDeveloper", "output": pd_plan}

            # Run dev team under PD supervision
            dev_outputs: dict[str, str] = {}

            # Step 1: Architecture
            if self._arch:
                arch_ctx = self._dev_context("SoftwareArchitect", requirement, ba_output, uiux_output, "", plan_context)
                yield {"type": "role_start", "role": "ProjectDeveloper"}
                pd_arch_task = await self._pd.run_task(
                    f"{arch_ctx}\n\n"
                    "Giao task cho SoftwareArchitect: thiết kế kiến trúc hệ thống tổng thể, "
                    "tech stack, system diagram, data flow, database design."
                )
                yield {"type": "role_done", "role": "ProjectDeveloper", "output": pd_arch_task}

                yield {"type": "role_start", "role": "SoftwareArchitect"}
                arch_output = await self._arch.run_task(
                    f"## Nhiệm vụ từ ProjectDeveloper\n{pd_arch_task}\n\n{arch_ctx}\n\n"
                    "Thiết kế kiến trúc hệ thống tổng thể."
                )
                dev_outputs["SoftwareArchitect"] = arch_output
                yield {"type": "role_done", "role": "SoftwareArchitect", "output": arch_output}

                # PD reviews arch
                yield {"type": "role_start", "role": "ProjectDeveloper"}
                pd_arch_review = await self._pd.run_task(
                    f"Architect vừa hoàn thành kiến trúc:\n{arch_output}\n\n"
                    "Đánh giá kiến trúc này có phù hợp với yêu cầu không? Ghi nhận và tiếp tục phân công."
                )
                yield {"type": "role_done", "role": "ProjectDeveloper", "output": pd_arch_review}
            else:
                arch_output = ""

            # Step 2: Security + DevOps (parallel, filtered context)
            phase2_coros = []
            phase2_keys = []

            if self._security:
                phase2_coros.append(
                    self._security.run_task(
                        self._dev_context("SecuritySpecialist", requirement, ba_output, uiux_output, arch_output, plan_context)
                        + "\nHãy thực hiện security review và threat modeling."
                    )
                )
                phase2_keys.append("SecuritySpecialist")
                yield {"type": "role_start", "role": "SecuritySpecialist"}

            if self._devops:
                phase2_coros.append(
                    self._devops.run_task(
                        self._dev_context("DevOpsEngineer", requirement, ba_output, uiux_output, arch_output, plan_context)
                        + "\nHãy thiết kế CI/CD pipeline và infrastructure."
                    )
                )
                phase2_keys.append("DevOpsEngineer")
                yield {"type": "role_start", "role": "DevOpsEngineer"}

            if phase2_coros:
                results = await asyncio.gather(*phase2_coros)
                for key, result in zip(phase2_keys, results):
                    dev_outputs[key] = result
                    yield {"type": "role_done", "role": key, "output": result}

            security_output = dev_outputs.get("SecuritySpecialist", "")

            # Step 3: FE + BE (parallel, filtered context)
            phase3_coros = []
            phase3_keys = []

            if self._fe:
                fe_ctx = self._dev_context("FrontendDev", requirement, ba_output, uiux_output, arch_output, plan_context)
                if security_output:
                    fe_ctx += f"\n\n## Security Guidelines\n{security_output}"
                phase3_coros.append(
                    self._fe.run_task(fe_ctx + "\nImplement frontend theo design spec và kiến trúc đã định.")
                )
                phase3_keys.append("FrontendDev")
                yield {"type": "role_start", "role": "FrontendDev"}

            if self._be:
                be_ctx = self._dev_context("BackendDev", requirement, ba_output, uiux_output, arch_output, plan_context)
                if security_output:
                    be_ctx += f"\n\n## Security Guidelines\n{security_output}"
                phase3_coros.append(
                    self._be.run_task(be_ctx + "\nImplement backend API và database theo kiến trúc đã định.")
                )
                phase3_keys.append("BackendDev")
                yield {"type": "role_start", "role": "BackendDev"}

            if phase3_coros:
                results = await asyncio.gather(*phase3_coros)
                for key, result in zip(phase3_keys, results):
                    dev_outputs[key] = result
                    yield {"type": "role_done", "role": key, "output": result}

            # Step 4: Tester (filtered context: BA AC + arch only)
            if self._tester:
                yield {"type": "role_start", "role": "Tester"}
                tester_ctx = self._dev_context("Tester", requirement, ba_output, uiux_output, arch_output, plan_context)
                all_impl = "\n\n".join(f"## {k}\n{v}" for k, v in dev_outputs.items())
                tester_output = await self._tester.run_task(
                    f"{tester_ctx}\n\n## Toàn bộ implementation\n{all_impl}\n\n"
                    "Lập test plan và viết test cases toàn diện."
                )
                dev_outputs["Tester"] = tester_output
                yield {"type": "role_done", "role": "Tester", "output": tester_output}

            outputs.update(dev_outputs)

            # PD compiles final report to PM
            yield {"type": "role_start", "role": "ProjectDeveloper"}
            all_dev = "\n\n".join(f"## {k}\n{v}" for k, v in dev_outputs.items())
            pd_report = await self._pd.run_task(
                f"Tất cả developer đã hoàn thành. Đây là output của từng người:\n\n{all_dev}\n\n"
                "Hãy tổng hợp và viết báo cáo gửi lên PM: những gì đã hoàn thành, "
                "chất lượng, và điểm cần lưu ý (nếu có)."
            )
            outputs["ProjectDeveloper_report"] = pd_report
            yield {"type": "role_done", "role": "ProjectDeveloper", "output": pd_report}

            # PM reviews dev results
            yield {"type": "role_start", "role": "ProductManager"}
            pm_review = await self._pm.run_task(
                f"## ProjectDeveloper báo cáo kết quả development:\n{pd_report}\n\n"
                f"## Yêu cầu gốc\n{requirement}\n\n"
                f"## BA Spec để đối chiếu\n{ba_output}\n\n"
                "Đánh giá: kết quả có đáp ứng yêu cầu không? "
                "Nếu OK thì nói 'CHẤP NHẬN'. "
                "Nếu cần sửa thì nói 'CẦN SỬA' kèm chỉ định role nào cần làm lại và tại sao."
            )
            yield {"type": "pm_review", "role": "ProductManager", "target": "Development",
                   "output": pm_review, "attempt": attempt + 1}

            if _pm_accepted(pm_review) or attempt >= MAX_RETRIES:
                break
            outputs["PM_feedback_dev"] = pm_review

        yield {"type": "phase_done", "phase": "3", "name": "Development"}

    # ------------------------------------------------------------------
    # Phase 4 — Final Report
    # ------------------------------------------------------------------

    async def _phase_report(
        self,
        requirement: str,
        outputs: dict,
    ) -> AsyncGenerator[dict, None]:
        yield {"type": "phase_start", "phase": "4", "name": "Final Report"}

        # PM assigns BA to write final report
        yield {"type": "role_start", "role": "ProductManager"}
        pm_assign = await self._pm.run_task(
            f"Development đã hoàn thành. Hãy giao task cho BusinessAnalyst: "
            "viết final report tổng hợp tất cả những gì team đã thực hiện và kết quả đạt được. "
            "Report cần ngắn gọn, dễ hiểu, dành cho người dùng cuối."
        )
        yield {"type": "role_done", "role": "ProductManager", "output": pm_assign}

        # Compile all outputs as context for BA
        all_outputs_summary = "\n\n".join(
            f"## {k}\n{v[:800]}..." if len(v) > 800 else f"## {k}\n{v}"
            for k, v in outputs.items()
            if not k.startswith("PM_feedback")
        )

        final_report = ""
        for attempt in range(MAX_RETRIES + 1):
            yield {"type": "role_start", "role": "BusinessAnalyst"}
            report_prompt = (
                f"## Yêu cầu từ PM\n{pm_assign}\n\n"
                f"## Yêu cầu gốc của user\n{requirement}\n\n"
                f"## Tổng hợp output của toàn bộ team\n{all_outputs_summary}\n\n"
                "Viết final report: Executive Summary, những gì đã làm được, "
                "tech stack, deliverables, và next steps."
            )
            if attempt > 0:
                report_prompt += f"\n\n## Phản hồi PM\n{outputs.get('PM_feedback_report', '')}\nHãy điều chỉnh."

            final_report = await self._reporter.run_task(report_prompt)
            outputs["FinalReport"] = final_report
            yield {"type": "role_done", "role": "BusinessAnalyst", "output": final_report}

            # PM final review
            yield {"type": "role_start", "role": "ProductManager"}
            pm_review = await self._pm.run_task(
                f"## BA vừa viết final report:\n{final_report}\n\n"
                "Đánh giá report này trước khi gửi cho user. "
                "Nếu OK thì nói 'CHẤP NHẬN' và thêm lời nhắn cuối cho user. "
                "Nếu cần sửa thì nói 'CẦN SỬA' kèm hướng dẫn."
            )
            yield {"type": "pm_review", "role": "ProductManager", "target": "FinalReport",
                   "output": pm_review, "attempt": attempt + 1}

            if _pm_accepted(pm_review) or attempt >= MAX_RETRIES:
                outputs["PM_closing"] = pm_review
                break
            outputs["PM_feedback_report"] = pm_review

        yield {"type": "phase_done", "phase": "4", "name": "Final Report"}


    # ------------------------------------------------------------------
    # Token optimization helpers
    # ------------------------------------------------------------------

    async def _compress(self, phase_name: str, output: str, word_limit: int = 300) -> str:
        """Ask PM to summarize a phase output to ~word_limit words.

        Used when compress_phases=True to reduce token usage passed between phases.
        """
        return await self._pm.run_task(
            f"Tóm tắt output của phase '{phase_name}' dưới đây trong khoảng {word_limit} từ. "
            f"Giữ lại các thông tin kỹ thuật và nghiệp vụ quan trọng nhất, bỏ phần mô tả thừa:\n\n{output}"
        )

    @staticmethod
    def _dev_context(
        role: str,
        requirement: str,
        ba_output: str,
        uiux_output: str,
        arch_output: str,
        plan_context: str,
    ) -> str:
        """Return only the context sections relevant to a specific dev role.

        Smart filtering: each role receives only what it actually needs,
        avoiding sending the full combined context (~5000+ tokens) to everyone.
        """
        req = f"## Yêu cầu dự án\n{requirement}"
        arch = f"## Kiến trúc hệ thống\n{arch_output}" if arch_output else ""
        ba = f"## BA Spec\n{ba_output}" if ba_output else ""
        uiux = f"## UI/UX Design\n{uiux_output}" if uiux_output else ""
        plan = f"## Kế hoạch tổng thể\n{plan_context}" if plan_context else ""

        role_parts: dict[str, list[str]] = {
            # Arch needs full picture to design the system
            "SoftwareArchitect":  [req, ba, uiux, plan],
            # Security needs BA (rules/auth) + arch, not UIUX wireframes
            "SecuritySpecialist": [req, ba, arch, plan],
            # DevOps only needs arch to set up infra/CI, not BA/UIUX details
            "DevOpsEngineer":     [req, arch, plan],
            # FE needs UIUX design + arch API contract, not BA business rules detail
            "FrontendDev":        [req, uiux, arch, plan],
            # BE needs BA spec + arch, not UIUX wireframes
            "BackendDev":         [req, ba, arch, plan],
            # Tester needs BA acceptance criteria + arch, not UIUX markup
            "Tester":             [req, ba, arch],
        }
        parts = role_parts.get(role, [req, arch])
        return "\n\n".join(p for p in parts if p)


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def _pm_accepted(pm_response: str) -> bool:
    """Return True if PM's response contains an acceptance signal."""
    keywords = ["chấp nhận", "accept", "ok", "approved", "✅", "đạt yêu cầu", "đồng ý"]
    lower = pm_response.lower()
    return any(kw in lower for kw in keywords)
