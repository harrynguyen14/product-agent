from __future__ import annotations

from roles.base_role import BaseRole


class ProjectDeveloper(BaseRole):
    role_name: str = "ProjectDeveloper"
    mention: str = "/pd"
    description: str = (
        "Project Developer — Tech Lead quản lý đội ngũ kỹ thuật. "
        "Nhận yêu cầu từ PM, phân công nhiệm vụ cho các developer, "
        "giám sát chất lượng từng bước, và báo cáo kết quả tổng hợp lên PM."
    )
    skill_file: str = "project_developer_skill.md"
