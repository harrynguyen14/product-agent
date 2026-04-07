from __future__ import annotations

from roles.base_role import BaseRole


class Reporter(BaseRole):
    role_name: str = "Reporter"
    mention: str = "/report"
    description: str = (
        "Reporter — tổng hợp output từ tất cả các roles thành tài liệu "
        "project hoàn chỉnh, rõ ràng và dễ đọc cho stakeholders."
    )
    skill_file: str = "reporter_skill.md"
