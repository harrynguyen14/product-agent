from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Optional

import discord
from discord.ext import commands

from config.settings import AppConfig
from core.discord_runner import DiscordEnvironmentRunner
from discord_bot.channel_manager import ChannelManager
from discord_bot.formatters import (
    format_plan,
    format_role_message,
    format_task_complete,
    format_thinking,
    format_error,
    split_message,
)
from discord_bot.review_gate import DiscordReviewGate, RoleReviewGate
from discord_bot.webhook_manager import WebhookManager
from flows.planning_flow import PlanningFlow
from infrastructure.logging import get_logger

logger = get_logger("discord_bot")

CONFIRM_WORDS = {"yes", "y", "confirm", "ok", "đồng ý", "chấp nhận"}

# Role slash-command map: /mention → display name
ROLE_MENTION_MAP = {
    "/pm":     "ProductManager",
    "/ba":     "BusinessAnalyst",
    "/uiux":   "UIUXDesigner",
    "/report": "Reporter",
    "/sec":    "SecuritySpecialist",
    "/devops": "DevOpsEngineer",
    "/fe":     "FrontendDev",
    "/be":     "BackendDev",
    "/arch":   "SoftwareArchitect",
    "/qa":     "Tester",
}


@dataclass
class TaskSession:
    """Tracks an active task channel session."""
    requirement: str
    task_channel_id: int
    roles: list[str] = field(default_factory=list)
    plan_tasks: list[dict] = field(default_factory=list)
    plan_text: str = ""
    is_complete: bool = False


@dataclass
class ChatSession:
    """Per-guild state."""
    guild_id: int
    main_channel_id: int
    review_gate: DiscordReviewGate = field(default_factory=DiscordReviewGate)
    role_review_gate: RoleReviewGate = field(default_factory=RoleReviewGate)
    active_task: Optional[TaskSession] = None
    runner: Optional[DiscordEnvironmentRunner] = None


class DiscordBot(commands.Bot):
    """Multi-agent Discord bot.

    **Main channel flow:**
    1. User sends requirement
    2. PM + Planner generate plan (no clarification)
    3. Bot posts plan → user types `yes` or feedback
    4. On accept → create task channel, run flows in background

    **Task channel flow:**
    - Roles post their work as messages
    - User can call roles with `/pm`, `/ba`, `/uiux`, `/arch`, etc.
    - On completion → PM tags user in main channel

    **Required Discord intents (must be enabled in Developer Portal):**
    - Message Content Intent (privileged)
    - Server Members Intent (optional, for @mentions)
    """

    def __init__(self, config: AppConfig) -> None:
        intents = discord.Intents.default()
        intents.message_content = True   # requires enabling in Developer Portal
        intents.guilds = True

        # Use a prefix that won't conflict with role slash-commands.
        # Role commands like /pm /ba etc. are handled manually in on_message.
        # Bot prefix commands (e.g. !status) use "!" to avoid confusion.
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )
        self.config = config
        self._sessions: dict[int, ChatSession] = {}
        self._webhooks = WebhookManager()

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------

    def _get_session(self, guild: discord.Guild, main_channel_id: int) -> ChatSession:
        if guild.id not in self._sessions:
            runner = DiscordEnvironmentRunner(config=self.config)
            self._sessions[guild.id] = ChatSession(
                guild_id=guild.id,
                main_channel_id=main_channel_id,
                runner=runner,
            )
        return self._sessions[guild.id]

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def on_ready(self) -> None:
        logger.info("discord_bot_ready", user=str(self.user))
        print(f"✅ Bot đã kết nối: {self.user}")
        print(f"📡 Servers: {[g.name for g in self.guilds]}")

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        self._webhooks.invalidate(channel.id)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.guild is None:
            return

        # Let discord.py handle !commands first
        await self.process_commands(message)

        content = message.content.strip()
        if not content:
            return

        guild = message.guild
        channel = message.channel
        main_ch_id = self.config.discord_main_channel_id or channel.id
        session = self._get_session(guild, main_ch_id)

        # --- Role slash-command (e.g. /ba, /pm, /arch ...) ---
        first_token = content.split()[0].lower()
        if first_token in ROLE_MENTION_MAP:
            await self._handle_role_mention(message, session, first_token, content)
            return

        # --- /help ---
        if content.lower() == "/help":
            await channel.send(self._help_text())
            return

        # --- Review gate: user replying to a plan ---
        if session.review_gate.is_armed:
            session.review_gate.resolve(content)
            return

        # --- Role review gate: user reviewing a completed role ---
        if (session.role_review_gate.is_armed
                and session.active_task
                and channel.id == session.active_task.task_channel_id):
            session.role_review_gate.resolve(content)
            return

        # --- Task channel: user talking to PM ---
        if (session.active_task
                and channel.id == session.active_task.task_channel_id
                and not session.active_task.is_complete):
            await self._relay_to_pm(message, session)
            return

        # --- Main channel: new requirement ---
        if main_ch_id and channel.id != main_ch_id:
            return   # ignore messages in other channels

        # Don't start a new task if one is already running
        if session.active_task and not session.active_task.is_complete:
            await channel.send(
                f"⏳ Đang có task đang thực thi trong "
                f"<#{session.active_task.task_channel_id}>.\n"
                "Vui lòng đợi hoàn thành trước khi tạo task mới."
            )
            return

        asyncio.create_task(self._run_planning(message, session))

    # ------------------------------------------------------------------
    # Planning (main channel)
    # ------------------------------------------------------------------

    async def _run_planning(
        self,
        message: discord.Message,
        session: ChatSession,
    ) -> None:
        requirement = message.content.strip()
        channel = message.channel
        guild = message.guild

        thinking_msg = await channel.send(
            format_thinking("ProductManager") + "\n*Đang phân tích yêu cầu và lập kế hoạch...*"
        )

        async def _on_plan_ready(plan_text: str, roles: list[str]) -> None:
            await channel.send(format_plan(plan_text))

        try:
            tasks, roles = await _run_planning_flow(
                runner=session.runner,
                requirement=requirement,
                review_gate=session.review_gate,
                on_plan_ready=_on_plan_ready,
            )
        except SystemExit:
            await channel.send("❌ Đã hủy.")
            return
        except Exception as e:
            logger.error("planning_error", error=str(e))
            await channel.send(format_error(str(e)))
            return
        finally:
            try:
                await thinking_msg.delete()
            except discord.HTTPException:
                pass

        # Create task channel
        mgr = ChannelManager(guild)
        task_id = mgr.generate_task_id()
        task_channel = await mgr.create_task_channel(task_id)

        plan_text = PlanningFlow._format_plan(tasks, roles) if tasks else ""
        session.active_task = TaskSession(
            requirement=requirement,
            task_channel_id=task_channel.id,
            roles=roles,
            plan_tasks=tasks,
            plan_text=plan_text,
        )

        roles_str = " | ".join(f"`{r}`" for r in roles)
        await channel.send(
            f"✅ **Plan được chấp nhận!**\n"
            f"📌 Task channel: {task_channel.mention}\n"
            f"👥 Roles: {roles_str}"
        )

        asyncio.create_task(
            self._run_task_execution(task_channel, channel, message.author, session)
        )

    # ------------------------------------------------------------------
    # Task execution (task channel)
    # ------------------------------------------------------------------

    async def _run_task_execution(
        self,
        task_channel: discord.TextChannel,
        main_channel: discord.TextChannel,
        user: discord.Member,
        session: ChatSession,
    ) -> None:
        task = session.active_task
        runner = session.runner
        gate = session.role_review_gate

        # Accumulated human feedback injected into the next role's context
        pending_feedback: str = ""

        # Roles that are internal coordinators — skip human review for these
        SKIP_REVIEW_ROLES = {"ProductManager", "ProjectDeveloper", "APP"}

        await self._webhooks.send(
            task_channel,
            "APP",
            f"🚀 **Bắt đầu thực thi**\n"
            f"📋 {task.requirement[:200]}\n"
            f"👥 Roles: {', '.join(task.roles)}\n\n"
            f"💬 Sau mỗi role hoàn thành, hãy reply `ok` để tiếp tục hoặc nhập feedback.",
        )

        try:
            async for event in runner.stream_product_flow(
                requirement=task.requirement,
                roles=task.roles,
                plan_context=task.plan_text,
            ):
                etype = event.get("type")

                if etype == "role_start":
                    role = event.get("role", "")
                    msg = format_thinking(role)
                    if pending_feedback and role not in SKIP_REVIEW_ROLES:
                        msg += f"\n\n> 💬 *Feedback từ user: {pending_feedback}*"
                        pending_feedback = ""
                    await self._webhooks.send(task_channel, role, msg)

                elif etype == "role_done":
                    role = event.get("role", "")
                    output = event.get("output", "")
                    await self._webhooks.send(task_channel, role, output)

                    # Pause for human review (skip internal coordinator roles)
                    if role not in SKIP_REVIEW_ROLES:
                        gate.arm()
                        await task_channel.send(
                            f"⏸️ **{role}** vừa hoàn thành.\n"
                            f"Reply `ok` để tiếp tục, hoặc nhập feedback để role tiếp theo biết."
                        )
                        try:
                            accepted, feedback = await gate.wait(timeout=300)
                            if feedback:
                                pending_feedback = feedback
                                await task_channel.send(
                                    f"📝 *Đã ghi nhận feedback. Chuyển sang bước tiếp theo...*"
                                )
                            else:
                                await task_channel.send(f"✅ *Tiếp tục...*")
                        except Exception:
                            await task_channel.send(f"⏭️ *Timeout — tự động tiếp tục...*")

                elif etype == "pm_review":
                    output = event.get("output", "")
                    attempt = event.get("attempt", 1)
                    target = event.get("target", "")
                    header = f"📋 **PM đánh giá** — {target} (lần {attempt})\n"
                    await self._webhooks.send(
                        task_channel, "ProductManager", header + output
                    )

                elif etype == "phase_start":
                    phase = event.get("phase", "")
                    name = event.get("name", "")
                    await self._webhooks.send(
                        task_channel, "APP",
                        f"── Giai đoạn {phase}: **{name}** ──"
                    )

                elif etype == "execution_done":
                    summary = event.get("summary", "Hoàn thành.")
                    await self._webhooks.send(
                        task_channel, "APP", f"✅ **Hoàn thành!**\n\n{summary}"
                    )
                    token_report = event.get("token_report", "")
                    if token_report:
                        await self._webhooks.send(task_channel, "APP", token_report)

                    task.is_complete = True
                    await main_channel.send(
                        format_task_complete(task_channel.mention, summary)
                        + f"\n\n{user.mention} Task của bạn đã hoàn thành!"
                    )

        except Exception as e:
            logger.error("task_execution_error", error=str(e))
            await task_channel.send(format_error(str(e)))
            await main_channel.send(
                f"❌ {user.mention} Task gặp lỗi: `{str(e)[:200]}`\n"
                f"Xem chi tiết tại {task_channel.mention}"
            )

    # ------------------------------------------------------------------
    # Role mention handler (/pm, /ba, /arch ...)
    # ------------------------------------------------------------------

    async def _handle_role_mention(
        self,
        message: discord.Message,
        session: ChatSession,
        mention: str,
        full_content: str,
    ) -> None:
        parts = full_content.split(None, 1)
        user_msg = parts[1].strip() if len(parts) > 1 else ""

        if not user_msg:
            await message.channel.send(
                f"💬 Vui lòng nhập nội dung sau lệnh `{mention}`\n"
                f"Ví dụ: `{mention} Câu hỏi hoặc yêu cầu của bạn`"
            )
            return

        task = session.active_task
        channel_context = ""
        if task:
            channel_context = (
                f"Yêu cầu dự án: {task.requirement}\n"
                f"Kế hoạch: {task.plan_text[:400]}"
            )

        async with message.channel.typing():
            try:
                response = await session.runner.handle_mention(
                    mention=mention,
                    user_message=user_msg,
                    channel_context=channel_context,
                )
            except Exception as e:
                logger.error("mention_error", mention=mention, error=str(e))
                await message.channel.send(format_error(str(e)))
                return

        display_name = ROLE_MENTION_MAP[mention]
        await self._webhooks.send(message.channel, display_name, response)

    # ------------------------------------------------------------------
    # Relay to PM in task channel
    # ------------------------------------------------------------------

    async def _relay_to_pm(
        self,
        message: discord.Message,
        session: ChatSession,
    ) -> None:
        task = session.active_task
        ctx = f"Requirement: {task.requirement}\nPlan: {task.plan_text[:300]}"
        async with message.channel.typing():
            try:
                response = await session.runner.handle_mention(
                    mention="/pm",
                    user_message=message.content,
                    channel_context=ctx,
                )
            except Exception as e:
                await message.channel.send(format_error(str(e)))
                return

        await self._webhooks.send(message.channel, "ProductManager", response)

    # ------------------------------------------------------------------
    # Help text
    # ------------------------------------------------------------------

    @staticmethod
    def _help_text() -> str:
        return (
            "**🤖 Multi-Agent Product Bot**\n\n"
            "**Kênh chính:** Gõ yêu cầu dự án để bắt đầu.\n"
            "Bot sẽ tạo plan và hỏi bạn xác nhận (`yes`) hoặc nhập feedback.\n\n"
            "**Trong kênh task — gọi role bằng `/mention`:**\n"
            "`/pm [nội dung]` — Product Manager\n"
            "`/ba [nội dung]` — Business Analyst\n"
            "`/uiux [nội dung]` — UI/UX Designer\n"
            "`/report [nội dung]` — Reporter\n"
            "`/arch [nội dung]` — Software Architect\n"
            "`/fe [nội dung]` — Frontend Dev\n"
            "`/be [nội dung]` — Backend Dev\n"
            "`/sec [nội dung]` — Security Specialist\n"
            "`/devops [nội dung]` — DevOps Engineer\n"
            "`/qa [nội dung]` — Tester\n\n"
            "**Bot commands:**\n"
            "`!status` — Xem trạng thái task hiện tại\n"
            "`/help` — Hiển thị tin nhắn này"
        )


# ------------------------------------------------------------------
# Standalone planning flow helper (avoids monkey-patching)
# ------------------------------------------------------------------

async def _run_planning_flow(
    runner: DiscordEnvironmentRunner,
    requirement: str,
    review_gate: Optional[DiscordReviewGate] = None,
    on_plan_ready=None,
) -> tuple[list[dict], list[str]]:
    pm = runner._registry.get("ProductManager")
    planner = runner._registry.get("Planner")

    flow = PlanningFlow(
        pm=pm,
        planner=planner,
        review_gate=review_gate,
        max_retries=runner.config.max_retries,
        on_plan_ready=on_plan_ready,
    )
    return await flow.run(requirement)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def run_bot(token: str, config: AppConfig) -> None:
    bot = DiscordBot(config=config)

    @bot.command(name="status")
    async def status_cmd(ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        session = bot._sessions.get(ctx.guild.id)
        if not session or not session.active_task:
            await ctx.send("ℹ️ Không có task đang chạy.")
            return
        task = session.active_task
        status_str = "✅ Hoàn thành" if task.is_complete else "⏳ Đang thực thi"
        await ctx.send(
            f"**Task hiện tại:** {task.requirement[:80]}\n"
            f"**Channel:** <#{task.task_channel_id}>\n"
            f"**Roles:** {', '.join(task.roles)}\n"
            f"**Trạng thái:** {status_str}"
        )

    bot.run(token)
