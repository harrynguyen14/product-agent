from __future__ import annotations

from typing import AsyncGenerator

from infrastructure.logging import get_logger
from roles.business_analyst import BusinessAnalyst
from roles.ui_ux_designer import UIUXDesigner
from roles.reporter import Reporter

logger = get_logger("ba_flow")


class BAFlow:
    """Business Analysis flow executed in a task channel.

    Flow:
        PM → BA (phân tích nghiệp vụ)
           → UIUXDesigner (thiết kế UI/UX dựa trên BA output)
           → Reporter (tổng hợp deliverable)

    Each role gets context from the previous role's output.
    Yields events for the Discord bot to relay as messages.
    """

    def __init__(
        self,
        ba: BusinessAnalyst,
        designer: UIUXDesigner,
        reporter: Reporter,
    ) -> None:
        self._ba = ba
        self._designer = designer
        self._reporter = reporter

    async def run(
        self,
        requirement: str,
        plan_context: str = "",
    ) -> dict[str, str]:
        """Execute the BA flow. Returns dict of outputs keyed by role_name."""
        outputs: dict[str, str] = {}

        # --- BA phase ---
        logger.info("ba_flow_ba_start")
        ba_prompt = (
            f"## Yêu cầu dự án\n{requirement}\n\n"
            + (f"## Kế hoạch tổng thể\n{plan_context}\n\n" if plan_context else "")
            + "Hãy phân tích nghiệp vụ và tạo functional specification đầy đủ."
        )
        ba_output = await self._ba.run_task(ba_prompt)
        outputs["BusinessAnalyst"] = ba_output
        logger.info("ba_flow_ba_done", length=len(ba_output))

        # --- UI/UX Design phase ---
        logger.info("ba_flow_uiux_start")
        uiux_prompt = (
            f"## Yêu cầu dự án\n{requirement}\n\n"
            f"## Phân tích nghiệp vụ từ BA\n{ba_output}\n\n"
            "Dựa trên phân tích trên, hãy thiết kế UI/UX chi tiết bao gồm "
            "wireframes, user journey và design system."
        )
        uiux_output = await self._designer.run_task(uiux_prompt)
        outputs["UIUXDesigner"] = uiux_output
        logger.info("ba_flow_uiux_done", length=len(uiux_output))

        # --- Reporter phase ---
        logger.info("ba_flow_reporter_start")
        report_prompt = (
            f"## Yêu cầu dự án\n{requirement}\n\n"
            f"## BA Output\n{ba_output}\n\n"
            f"## UI/UX Design Output\n{uiux_output}\n\n"
            "Hãy tổng hợp tất cả thành một project report hoàn chỉnh."
        )
        report_output = await self._reporter.run_task(report_prompt)
        outputs["Reporter"] = report_output
        logger.info("ba_flow_reporter_done", length=len(report_output))

        return outputs

    async def stream(
        self,
        requirement: str,
        plan_context: str = "",
    ) -> AsyncGenerator[dict, None]:
        """Stream events as each role completes its work."""
        outputs: dict[str, str] = {}

        # BA
        yield {"type": "role_start", "role": "BusinessAnalyst"}
        ba_prompt = (
            f"## Yêu cầu dự án\n{requirement}\n\n"
            + (f"## Kế hoạch tổng thể\n{plan_context}\n\n" if plan_context else "")
            + "Hãy phân tích nghiệp vụ và tạo functional specification đầy đủ."
        )
        ba_output = await self._ba.run_task(ba_prompt)
        outputs["BusinessAnalyst"] = ba_output
        yield {"type": "role_done", "role": "BusinessAnalyst", "output": ba_output}

        # UI/UX
        yield {"type": "role_start", "role": "UIUXDesigner"}
        uiux_prompt = (
            f"## Yêu cầu dự án\n{requirement}\n\n"
            f"## Phân tích nghiệp vụ từ BA\n{ba_output}\n\n"
            "Thiết kế UI/UX chi tiết bao gồm wireframes, user journey và design system."
        )
        uiux_output = await self._designer.run_task(uiux_prompt)
        outputs["UIUXDesigner"] = uiux_output
        yield {"type": "role_done", "role": "UIUXDesigner", "output": uiux_output}

        # Reporter
        yield {"type": "role_start", "role": "Reporter"}
        report_prompt = (
            f"## Yêu cầu dự án\n{requirement}\n\n"
            f"## BA Output\n{ba_output}\n\n"
            f"## UI/UX Design Output\n{uiux_output}\n\n"
            "Tổng hợp tất cả thành project report hoàn chỉnh."
        )
        report_output = await self._reporter.run_task(report_prompt)
        outputs["Reporter"] = report_output
        yield {"type": "role_done", "role": "Reporter", "output": report_output}

        yield {"type": "flow_done", "flow": "ba_flow", "outputs": outputs}
