from __future__ import annotations

import uuid
from typing import Optional

import discord
from discord import Guild, TextChannel, CategoryChannel, PermissionOverwrite

from infrastructure.logging import get_logger

logger = get_logger("channel_manager")

TASK_CATEGORY_NAME = "TASKS"


class ChannelManager:
    """Creates and manages Discord task channels.

    Each accepted plan gets its own text channel under the TASKS category.
    The PM role and relevant specialist roles are invited by name via bot messages.
    """

    def __init__(self, guild: Guild) -> None:
        self._guild = guild

    async def get_or_create_category(self) -> CategoryChannel:
        for cat in self._guild.categories:
            if cat.name.upper() == TASK_CATEGORY_NAME:
                return cat
        category = await self._guild.create_category(TASK_CATEGORY_NAME)
        logger.info("category_created", name=TASK_CATEGORY_NAME)
        return category

    async def create_task_channel(self, task_id: str) -> TextChannel:
        """Create a new channel #task-{short_id} under the TASKS category."""
        category = await self.get_or_create_category()
        short_id = task_id[:8] if len(task_id) > 8 else task_id
        channel_name = f"task-{short_id}"

        # Check if channel already exists
        existing = discord.utils.get(self._guild.text_channels, name=channel_name)
        if existing:
            return existing

        channel = await self._guild.create_text_channel(
            name=channel_name,
            category=category,
            topic=f"Task {task_id} — auto-created by ProductManager",
        )
        logger.info("task_channel_created", channel=channel_name, id=channel.id)
        return channel

    async def archive_task_channel(self, channel: TextChannel) -> None:
        """Move channel to ARCHIVED category (soft delete)."""
        archive_cat_name = "ARCHIVED"
        archive_cat = discord.utils.get(self._guild.categories, name=archive_cat_name)
        if not archive_cat:
            archive_cat = await self._guild.create_category(archive_cat_name)
        await channel.edit(category=archive_cat)
        logger.info("task_channel_archived", channel=channel.name)

    async def get_main_channel(self, channel_id: int) -> Optional[TextChannel]:
        ch = self._guild.get_channel(channel_id)
        if isinstance(ch, TextChannel):
            return ch
        # Fallback: find first general/main channel
        for ch in self._guild.text_channels:
            if ch.name in ("general", "main", "chat"):
                return ch
        return self._guild.text_channels[0] if self._guild.text_channels else None

    def generate_task_id(self) -> str:
        return uuid.uuid4().hex[:8]
