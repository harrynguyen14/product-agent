from __future__ import annotations

import json
import re
from typing import Any, AsyncGenerator, Callable, Optional, TYPE_CHECKING

from infrastructure.logging import get_logger
from roles.product_manager import ProductManager
from roles.planner import RolePlanner
from plan.ask_review import AskReview, ReviewConst

if TYPE_CHECKING:
    from discord_bot.review_gate import DiscordReviewGate

logger = get_logger("planning_flow")

# Roles cần cho từng loại dự án (PM tự quyết định)
_ROLE_HINTS = """
Dựa trên loại dự án, hãy chọn roles phù hợp từ danh sách sau:
- ProductManager: luôn có mặt
- BusinessAnalyst: khi cần phân tích nghiệp vụ phức tạp
- UIUXDesigner: khi dự án có UI/frontend
- Reporter: khi cần tổng hợp tài liệu deliverable
- SoftwareArchitect: khi cần thiết kế hệ thống phức tạp
- SecuritySpecialist: khi dự án production hoặc xử lý dữ liệu nhạy cảm
- DevOpsEngineer: khi cần CI/CD, deployment, infrastructure
- FrontendDev: khi có frontend implementation
- BackendDev: khi có backend/API implementation
- Tester: luôn nên có để đảm bảo chất lượng
"""


class PlanningFlow:
    """Orchestrates the main-channel planning loop.

    Flow:
        1. User sends requirement to main channel
        2. PM acknowledges and asks Planner to generate a plan (no clarification)
        3. PM presents the plan to user in main channel
        4. User reviews: 'yes' to accept, or feedback to revise
        5. On accept: returns (plan_data, roles_needed)
    """

    def __init__(
        self,
        pm: ProductManager,
        planner: RolePlanner,
        review_gate: Optional["DiscordReviewGate"] = None,
        max_retries: int = 3,
        on_plan_ready: Optional[Callable[[str, list[str]], Any]] = None,
    ) -> None:
        self._pm = pm
        self._planner = planner
        self._review_gate = review_gate
        self._max_retries = max_retries
        self._on_plan_ready = on_plan_ready  # callback(plan_text, roles) when plan is ready

    async def run(self, requirement: str) -> tuple[list[dict], list[str]]:
        """Run the planning loop. Returns (task_list, roles_needed).

        Blocks until the user accepts the plan.
        """
        logger.info("planning_flow_start", requirement=requirement[:80])

        # PM acknowledges
        pm_ack = await self._pm.respond(
            f"Tôi vừa nhận được yêu cầu: '{requirement}'\n"
            "Đang phân tích và lập kế hoạch..."
        )
        logger.info("pm_ack", content=pm_ack[:80])

        retries = 0
        feedback = ""
        last_plan: list[dict] = []

        while retries <= self._max_retries:
            # Planner generates plan
            plan_prompt = requirement
            if feedback:
                plan_prompt = f"{requirement}\n\n## Feedback từ user:\n{feedback}"

            logger.info("planner_generating", attempt=retries + 1)
            tasks = await self._planner.generate_plan(plan_prompt)
            last_plan = tasks

            # PM decides which roles are needed
            roles = await self._extract_roles(tasks)

            # Format plan for display
            plan_text = self._format_plan(tasks, roles)

            logger.info("plan_ready", tasks=len(tasks), roles=roles)

            # Notify caller (e.g. Discord bot sends message to channel)
            if self._on_plan_ready:
                await self._on_plan_ready(plan_text, roles)

            # Ask user to review
            review_gate = _DiscordGateAdapter(self._review_gate) if self._review_gate else None
            ask = AskReview(review_gate)
            user_input, confirmed = await ask.run(plan_text)

            if confirmed:
                logger.info("plan_accepted", tasks=len(tasks))
                return last_plan, roles

            # User gave feedback — retry
            feedback = user_input
            retries += 1
            logger.info("plan_rejected", feedback=feedback[:80], attempt=retries)

        # Exhausted retries — use last plan
        logger.warning("plan_retries_exhausted", using_last=True)
        roles = await self._extract_roles(last_plan)
        return last_plan, roles

    async def stream(self, requirement: str) -> AsyncGenerator[dict, None]:
        """Stream events during planning."""
        yield {"type": "role_start", "role": "ProductManager"}

        plan_ready_data: dict = {}

        async def _on_plan_ready(plan_text: str, roles: list[str]) -> None:
            plan_ready_data["text"] = plan_text
            plan_ready_data["roles"] = roles

        flow = PlanningFlow(
            pm=self._pm,
            planner=self._planner,
            review_gate=self._review_gate,
            max_retries=self._max_retries,
            on_plan_ready=_on_plan_ready,
        )

        tasks, roles = await flow.run(requirement)

        yield {"type": "plan_ready", "plan": plan_ready_data.get("text", ""), "roles": roles}
        yield {"type": "planning_done", "tasks": tasks, "roles": roles}

    async def _extract_roles(self, tasks: list[dict]) -> list[str]:
        """Ask PM to determine which roles are needed based on the task list."""
        task_summary = "\n".join(
            f"- {t.get('role', '?')}: {t.get('instruction', '')[:60]}"
            for t in tasks
        )
        response = await self._pm.respond(
            f"Dựa trên các tasks sau, liệt kê các roles cần thiết (chỉ tên, cách nhau bằng dấu phẩy):\n"
            f"{task_summary}\n\n{_ROLE_HINTS}"
        )
        return self._parse_roles(response)

    @staticmethod
    def _parse_roles(response: str) -> list[str]:
        """Extract role names from PM response."""
        valid_roles = {
            "ProductManager", "BusinessAnalyst", "UIUXDesigner", "Reporter",
            "SoftwareArchitect", "SecuritySpecialist", "DevOpsEngineer",
            "FrontendDev", "BackendDev", "Tester",
        }
        found = []
        for role in valid_roles:
            if role.lower() in response.lower():
                found.append(role)
        # PM is always included
        if "ProductManager" not in found:
            found.insert(0, "ProductManager")
        return found

    @staticmethod
    def _format_plan(tasks: list[dict], roles: list[str]) -> str:
        lines = ["**Kế hoạch dự án:**\n"]
        for i, task in enumerate(tasks, 1):
            role = task.get("role", "?")
            instruction = task.get("instruction", "")
            deps = task.get("dependent_task_ids", [])
            dep_str = f" ← phụ thuộc: {', '.join(deps)}" if deps else ""
            lines.append(f"{i}. **[{role}]** {instruction}{dep_str}")

        lines.append(f"\n**Roles tham gia:** {', '.join(roles)}")
        return "\n".join(lines)


class _DiscordGateAdapter:
    """Adapts DiscordReviewGate to the interface expected by AskReview."""

    def __init__(self, gate: "DiscordReviewGate") -> None:
        self._gate = gate

    def arm(self) -> None:
        self._gate.arm()

    async def wait(self, timeout: float = 600) -> str:
        return await self._gate.wait(timeout=timeout)
