from __future__ import annotations

TG_MAX = 4096
CHUNK_SIZE = 3900  # safe margin dưới 4096

# Emoji header mỗi role
ROLE_HEADERS: dict[str, str] = {
    "ProductManager":    "🧑‍💼 <b>Product Manager</b>",
    "Planner":           "📐 <b>Planner</b>",
    "BusinessAnalyst":   "📊 <b>Business Analyst</b>",
    "UIUXDesigner":      "🎨 <b>UI/UX Designer</b>",
    "ProjectDeveloper":  "🏗 <b>Project Developer</b>",
    "SoftwareArchitect": "🏛 <b>Software Architect</b>",
    "SecuritySpecialist":"🔒 <b>Security Specialist</b>",
    "DevOpsEngineer":    "⚙️ <b>DevOps Engineer</b>",
    "FrontendDev":       "🖥 <b>Frontend Developer</b>",
    "BackendDev":        "🗄 <b>Backend Developer</b>",
    "Tester":            "🧪 <b>Tester / QA</b>",
    "Reporter":          "📝 <b>Reporter</b>",
    "VietnameseTranslator": "🌐 <b>Translator</b>",
}


def split_message(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """Split text thành các chunk <= chunk_size ký tự."""
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= chunk_size:
            chunks.append(text)
            break
        # Cắt tại newline gần nhất trước chunk_size
        split_at = text.rfind("\n", 0, chunk_size)
        if split_at == -1:
            split_at = chunk_size
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


def format_role_header(role_name: str) -> str:
    return ROLE_HEADERS.get(role_name, f"🤖 <b>{role_name}</b>")


def format_gate_prompt(role_name: str, instruction: str) -> str:
    """Tin nhắn hỏi user trước khi role bắt đầu làm."""
    header = format_role_header(role_name)
    return (
        f"{header} sắp thực hiện:\n"
        f"<i>{_truncate(instruction, 300)}</i>\n\n"
        "Gõ <code>ok</code> để tiếp tục, hoặc gõ góp ý để điều chỉnh."
    )


def format_role_output(role_name: str, output: str) -> str:
    """Header + output của role."""
    header = format_role_header(role_name)
    return f"{header}\n\n{output}"


def format_thinking(role_name: str) -> str:
    header = format_role_header(role_name)
    return f"{header} đang xử lý..."


def format_error(exc: Exception) -> str:
    return f"❌ <b>Lỗi:</b> <code>{str(exc)[:500]}</code>"


def format_done() -> str:
    return "✅ <b>Hoàn thành!</b> Tất cả các role đã thực thi xong."


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."
