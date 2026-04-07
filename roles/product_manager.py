from __future__ import annotations

from roles.base_role import BaseRole


class ProductManager(BaseRole):
    role_name: str = "ProductManager"
    mention: str = "/pm"
    description: str = (
        "Product Manager — điều phối dự án, lắng nghe yêu cầu user, "
        "lập kế hoạch và phân công công việc cho team. "
        "Báo cáo kết quả về cho user khi hoàn thành."
    )
    skill_file: str = "pm_skill.md"
