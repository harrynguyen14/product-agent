from __future__ import annotations

import json
from typing import Any

from roles.base_role import BaseRole


class RolePlanner(BaseRole):
    """Internal planner role — generates structured task plans as JSON.

    Not exposed directly to Discord users; used internally by PlanningFlow
    to produce the task breakdown that the PM presents.
    """

    role_name: str = "Planner"
    mention: str = "/planner"
    description: str = (
        "Chuyên gia lập kế hoạch kỹ thuật — phân tích yêu cầu và tạo task plan "
        "chi tiết với role assignments và dependencies."
    )
    skill_file: str = "planner_skill.md"

    async def generate_plan(self, requirement: str) -> list[dict[str, Any]]:
        """Generate a structured plan as a list of task dicts."""
        prompt = (
            f"## Yêu cầu dự án\n{requirement}\n\n"
            "Hãy tạo một plan chi tiết cho dự án này. "
            "Output PHẢI là JSON array theo đúng format được định nghĩa trong skill."
        )
        raw = await self.respond(prompt)

        # Extract JSON from response
        try:
            # Try to find JSON block
            import re
            match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            # Try parsing entire response as JSON
            return json.loads(raw)
        except (json.JSONDecodeError, AttributeError):
            # Fallback: return raw as a single task
            return [{"task_id": "1", "role": "ProductManager",
                     "instruction": raw, "dependent_task_ids": [], "priority": "high"}]
