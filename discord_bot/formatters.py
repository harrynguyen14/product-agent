from __future__ import annotations

from typing import Any


MAX_DISCORD_LENGTH = 1900  # leave room below 2000 char limit


def split_message(text: str, max_len: int = MAX_DISCORD_LENGTH) -> list[str]:
    """Split a long message into chunks that fit Discord's 2000-char limit."""
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        chunk = text[:max_len]
        # Try to break at newline boundary
        break_at = chunk.rfind("\n")
        if break_at > max_len // 2:
            chunk = text[:break_at]
        chunks.append(chunk)
        text = text[len(chunk):]
    return chunks


def format_plan(plan_text: str) -> str:
    return (
        "📋 **Plan đã được tạo:**\n"
        "```\n"
        f"{plan_text}\n"
        "```\n"
        "✅ Gõ `yes` để xác nhận  |  💬 Hoặc nhập feedback để chỉnh sửa"
    )


def format_role_message(role_name: str, content: str, *, use_webhook: bool = True) -> str:
    """Format nội dung message của một role.

    Khi use_webhook=True (mặc định), bỏ header vì webhook đã hiển thị
    username và avatar riêng của từng agent.
    Khi use_webhook=False (fallback), thêm header icon + tên.
    """
    if use_webhook:
        return content

    icons = {
        "ProductManager":       "🎯",
        "Planner":              "🗂️",
        "BusinessAnalyst":      "📊",
        "UIUXDesigner":         "🎨",
        "Reporter":             "📝",
        "SecuritySpecialist":   "🔒",
        "DevOpsEngineer":       "⚙️",
        "FrontendDev":          "💻",
        "BackendDev":           "🖥️",
        "SoftwareArchitect":    "🏗️",
        "Tester":               "🧪",
    }
    icon = icons.get(role_name, "🤖")
    return f"{icon} **{role_name}**\n{content}"


def format_task_complete(task_channel: str, summary: str) -> str:
    return (
        f"✅ Task đã hoàn thành trong {task_channel}\n\n"
        f"**Tóm tắt:**\n{summary}"
    )


def format_error(error: str) -> str:
    return f"❌ **Lỗi:** {error}"


def format_thinking(role_name: str, *, use_webhook: bool = True) -> str:
    """Trạng thái 'đang xử lý'.

    Khi use_webhook=True, chỉ trả về nội dung — webhook tự hiển thị username.
    """
    if use_webhook:
        return "*đang xử lý...*"

    icons = {
        "ProductManager":       "🎯",
        "BusinessAnalyst":      "📊",
        "UIUXDesigner":         "🎨",
        "SecuritySpecialist":   "🔒",
        "DevOpsEngineer":       "⚙️",
        "FrontendDev":          "💻",
        "BackendDev":           "🖥️",
        "SoftwareArchitect":    "🏗️",
        "Tester":               "🧪",
        "Reporter":             "📝",
    }
    icon = icons.get(role_name, "🤖")
    return f"{icon} *{role_name} đang xử lý...*"
