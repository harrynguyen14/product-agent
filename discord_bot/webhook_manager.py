from __future__ import annotations

"""WebhookManager — mỗi agent gửi message qua webhook riêng.

Mỗi agent có username và avatar_url khác nhau, tạo cảm giác
như nhiều người đang chat trong cùng một channel.
"""

import asyncio
from typing import Optional

import discord

from infrastructure.logging import get_logger

logger = get_logger("webhook_manager")

# Avatar URL công khai cho từng role (dùng DiceBear Avatars — không cần upload)
_AVATAR_BASE = "https://api.dicebear.com/8.x/bottts-neutral/png?seed={seed}&size=128"

AGENT_PROFILES: dict[str, dict] = {
    "ProductManager": {
        "username": "Product Manager 🎯",
        "avatar_url": _AVATAR_BASE.format(seed="ProductManager"),
    },
    "BusinessAnalyst": {
        "username": "Business Analyst 📊",
        "avatar_url": _AVATAR_BASE.format(seed="BusinessAnalyst"),
    },
    "UIUXDesigner": {
        "username": "UI/UX Designer 🎨",
        "avatar_url": _AVATAR_BASE.format(seed="UIUXDesigner"),
    },
    "Reporter": {
        "username": "Reporter 📝",
        "avatar_url": _AVATAR_BASE.format(seed="Reporter"),
    },
    "SecuritySpecialist": {
        "username": "Security Specialist 🔒",
        "avatar_url": _AVATAR_BASE.format(seed="SecuritySpecialist"),
    },
    "DevOpsEngineer": {
        "username": "DevOps Engineer ⚙️",
        "avatar_url": _AVATAR_BASE.format(seed="DevOpsEngineer"),
    },
    "FrontendDev": {
        "username": "Frontend Dev 💻",
        "avatar_url": _AVATAR_BASE.format(seed="FrontendDev"),
    },
    "BackendDev": {
        "username": "Backend Dev 🖥️",
        "avatar_url": _AVATAR_BASE.format(seed="BackendDev"),
    },
    "SoftwareArchitect": {
        "username": "Software Architect 🏗️",
        "avatar_url": _AVATAR_BASE.format(seed="SoftwareArchitect"),
    },
    "Tester": {
        "username": "Tester 🧪",
        "avatar_url": _AVATAR_BASE.format(seed="Tester"),
    },
    "Planner": {
        "username": "Planner 🗂️",
        "avatar_url": _AVATAR_BASE.format(seed="Planner"),
    },
    "ProjectDeveloper": {
        "username": "Project Developer 🚀",
        "avatar_url": _AVATAR_BASE.format(seed="ProjectDeveloper"),
    },
    "APP": {
        "username": "APP 🤖",
        "avatar_url": _AVATAR_BASE.format(seed="APP"),
    },
}

_DEFAULT_PROFILE = {"username": "Agent 🤖", "avatar_url": _AVATAR_BASE.format(seed="default")}


class WebhookManager:
    """Cache và tái sử dụng Discord webhooks theo channel.

    Mỗi channel tạo tối đa 1 webhook (tên "AgentHub").
    Khi gửi message, chúng ta override username/avatar_url
    để mỗi agent trông như một user khác nhau.
    """

    def __init__(self) -> None:
        # channel_id -> discord.Webhook
        self._cache: dict[int, discord.Webhook] = {}
        self._lock = asyncio.Lock()

    async def get_webhook(self, channel: discord.TextChannel) -> discord.Webhook:
        """Trả về webhook cho channel, tạo mới nếu chưa có."""
        async with self._lock:
            if channel.id in self._cache:
                return self._cache[channel.id]

            # Kiểm tra webhook cũ của bot trong channel này
            try:
                existing = await channel.webhooks()
                for wh in existing:
                    if wh.name == "AgentHub":
                        self._cache[channel.id] = wh
                        logger.info("webhook_reused", channel=channel.name)
                        return wh
            except discord.Forbidden:
                logger.warning("webhook_no_permission", channel=channel.name)
                return None

            # Tạo mới
            try:
                wh = await channel.create_webhook(name="AgentHub")
                self._cache[channel.id] = wh
                logger.info("webhook_created", channel=channel.name)
                return wh
            except discord.Forbidden:
                logger.warning("webhook_create_failed", channel=channel.name)
                return None

    async def send(
        self,
        channel: discord.TextChannel,
        role_name: str,
        content: str,
        *,
        max_len: int = 1900,
    ) -> None:
        """Gửi message với identity của role_name.

        Nếu không lấy được webhook (thiếu quyền), fallback về channel.send.
        """
        webhook = await self.get_webhook(channel)
        profile = AGENT_PROFILES.get(role_name, _DEFAULT_PROFILE)

        chunks = _split(content, max_len)

        if webhook is None:
            # Fallback: gửi bình thường với header tên role
            for chunk in chunks:
                await channel.send(f"**{profile['username']}**\n{chunk}")
            return

        for chunk in chunks:
            try:
                await webhook.send(
                    content=chunk,
                    username=profile["username"],
                    avatar_url=profile["avatar_url"],
                )
            except discord.HTTPException as e:
                logger.warning("webhook_send_failed", error=str(e))
                await channel.send(f"**{profile['username']}**\n{chunk}")

    def invalidate(self, channel_id: int) -> None:
        """Xóa cache khi channel bị xóa."""
        self._cache.pop(channel_id, None)


def _split(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        chunk = text[:max_len]
        break_at = chunk.rfind("\n")
        if break_at > max_len // 2:
            chunk = text[:break_at]
        chunks.append(chunk)
        text = text[len(chunk):]
    return chunks
