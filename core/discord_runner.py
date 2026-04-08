from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional

from actions.action import LLMCallable
from config.settings import AppConfig
from core.llm_factory import LLMFactory, MultiModelSet
from flows.ba_flow import BAFlow
from flows.pd_flow import PDFlow
from flows.planning_flow import PlanningFlow
from flows.product_flow import ProductFlow
from infrastructure.logging import get_logger
from roles.business_analyst import BusinessAnalyst
from roles.devops_engineer import DevOpsEngineer
from roles.frontend_dev import FrontendDev
from roles.backend_dev import BackendDev
from roles.planner import RolePlanner
from roles.product_manager import ProductManager
from roles.project_developer import ProjectDeveloper
from roles.registry import RoleRegistry
from roles.reporter import Reporter
from roles.security_specialist import SecuritySpecialist
from roles.software_architect import SoftwareArchitect
from roles.tester import Tester
from roles.ui_ux_designer import UIUXDesigner

if TYPE_CHECKING:
    from discord_bot.review_gate import DiscordReviewGate

logger = get_logger("discord_runner")

# Roles that belong to the BA flow
BA_FLOW_ROLES = {"BusinessAnalyst", "UIUXDesigner", "Reporter"}

# Roles that belong to the PD flow
PD_FLOW_ROLES = {"SoftwareArchitect", "SecuritySpecialist", "DevOpsEngineer",
                 "FrontendDev", "BackendDev", "Tester"}


class DiscordEnvironmentRunner:
    """Orchestrates the full Discord multi-agent workflow.

    Main channel:
        1. Receives user requirement
        2. Runs PlanningFlow (PM + Planner → plan → user review)
        3. Creates task channel and invites relevant roles

    Task channel:
        4. Runs BAFlow (if BA roles are needed)
        5. Runs PDFlow (if PD roles are needed)
        6. PM summarizes and notifies user in main channel
    """

    def __init__(
        self,
        config: AppConfig,
        llm: Optional[LLMCallable] = None,
    ) -> None:
        self.config = config

        # Keep the raw LangChain model so TokenTracker.wrap() can read usage_metadata
        self._raw_llm = LLMFactory.build_raw(config)
        self._llm: LLMCallable = llm or LLMFactory.build(config)

        # Token tracker — one per runner, reset at start of each task
        from infrastructure.token_tracker import TokenTracker
        self.token_tracker = TokenTracker()

        # Multi-model set (None = single-model mode, backward compatible)
        multi_set: Optional[MultiModelSet] = None
        if getattr(config, "multi_model_enabled", False):
            multi_set = LLMFactory.build_multi(config)
            logger.info(
                "multi_model_enabled",
                claude=config.anthropic_multi_provider,
                gemini25=config.gemini_reasoning_provider,
                gemini20=config.gemini_fast_provider,
            )

        # Load default tools (web_search) and inject into all roles
        from tools.registry import build_default_registry as build_tool_registry
        _tool_registry = build_tool_registry()
        self._registry = RoleRegistry(
            self._llm,
            tools=_tool_registry.all_tools(),
            tracker=self.token_tracker,
            raw_llm=self._raw_llm,
            multi_model_set=multi_set,
            history_window=getattr(config, "role_history_window", 10),
            react_history_window=getattr(config, "role_react_history_window", 6),
        )

    # ------------------------------------------------------------------
    # Public: stream events for Discord bot
    # ------------------------------------------------------------------

    async def stream_planning(
        self,
        requirement: str,
        review_gate: Optional["DiscordReviewGate"] = None,
        on_plan_ready: Optional[Any] = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream planning phase events (main channel).

        Yields:
            role_start    → role is thinking
            plan_ready    → plan text + roles list
            planning_done → plan accepted, tasks + roles returned
        """
        pm: ProductManager = self._registry.get("ProductManager")
        planner: RolePlanner = self._registry.get("Planner")

        flow = PlanningFlow(
            pm=pm,
            planner=planner,
            review_gate=review_gate,
            max_retries=self.config.max_retries,
            on_plan_ready=on_plan_ready,
        )

        yield {"type": "role_start", "role": "ProductManager"}

        tasks, roles = await flow.run(requirement)

        yield {
            "type": "planning_done",
            "tasks": tasks,
            "roles": roles,
            "requirement": requirement,
        }

    async def stream_task_execution(
        self,
        requirement: str,
        roles: list[str],
        plan_context: str = "",
    ) -> AsyncGenerator[dict, None]:
        """Stream task channel execution events.

        Runs BA flow and/or PD flow based on which roles are needed.

        Yields:
            role_start      → role begins working
            role_done       → role finished, output included
            flow_done       → a sub-flow completed
            execution_done  → entire execution finished, summary included
        """
        ba_outputs: dict[str, str] = {}
        pd_outputs: dict[str, str] = {}

        roles_set = set(roles)

        # --- BA Flow ---
        ba_roles_needed = roles_set & BA_FLOW_ROLES
        if ba_roles_needed:
            logger.info("starting_ba_flow", roles=list(ba_roles_needed))

            ba = self._registry.get("BusinessAnalyst") if "BusinessAnalyst" in ba_roles_needed else None
            designer = self._registry.get("UIUXDesigner") if "UIUXDesigner" in ba_roles_needed else None
            reporter = self._registry.get("Reporter") if "Reporter" in ba_roles_needed else None

            # We need at least BA to run the flow
            if ba:
                ba_flow = BAFlow(
                    ba=ba,
                    designer=designer or self._registry.get("UIUXDesigner"),
                    reporter=reporter or self._registry.get("Reporter"),
                )
                async for event in ba_flow.stream(requirement, plan_context=plan_context):
                    yield event
                    if event["type"] == "flow_done":
                        ba_outputs = event.get("outputs", {})

        # --- PD Flow ---
        pd_roles_needed = roles_set & PD_FLOW_ROLES
        if pd_roles_needed:
            logger.info("starting_pd_flow", roles=list(pd_roles_needed))

            ba_context = "\n\n".join(
                f"## {k}\n{v}" for k, v in ba_outputs.items()
            ) if ba_outputs else ""

            pd_flow = PDFlow(
                architect=self._registry.get("SoftwareArchitect") if "SoftwareArchitect" in pd_roles_needed else None,
                security=self._registry.get("SecuritySpecialist") if "SecuritySpecialist" in pd_roles_needed else None,
                devops=self._registry.get("DevOpsEngineer") if "DevOpsEngineer" in pd_roles_needed else None,
                fe_dev=self._registry.get("FrontendDev") if "FrontendDev" in pd_roles_needed else None,
                be_dev=self._registry.get("BackendDev") if "BackendDev" in pd_roles_needed else None,
                tester=self._registry.get("Tester") if "Tester" in pd_roles_needed else None,
            )

            async for event in pd_flow.stream(requirement, ba_context=ba_context, plan_context=plan_context):
                yield event
                if event["type"] == "flow_done":
                    pd_outputs = event.get("outputs", {})

        # --- Final summary by PM ---
        all_outputs = {**ba_outputs, **pd_outputs}
        summary = await self._pm_summarize(requirement, all_outputs)

        yield {
            "type": "execution_done",
            "summary": summary,
            "outputs": all_outputs,
        }

    async def stream_product_flow(
        self,
        requirement: str,
        roles: list[str],
        plan_context: str = "",
        *,
        reset_tracker: bool = True,
    ) -> AsyncGenerator[dict, None]:
        """Stream the PM-orchestrated ProductFlow.

        This is the new flow where PM acts as central coordinator:
            Phase 1: PM → BA (review loop)
            Phase 2: PM → UIUXDesigner (review loop, cross-check with BA)
            Phase 3: PM → ProjectDeveloper → dev team → PM review
            Phase 4: PM → BA writes final report → PM review → user

        Event types passed through to Discord bot:
            role_start, role_done  — same as before (webhook renders per-agent)
            pm_review              — PM evaluation message
            phase_start/phase_done — phase boundary markers
            flow_done              — entire flow done
        """
        if reset_tracker:
            self.token_tracker.reset()

        roles_set = set(roles)

        flow = ProductFlow(
            pm=self._registry.get("ProductManager"),
            ba=self._registry.get("BusinessAnalyst"),
            designer=self._registry.get("UIUXDesigner"),
            pd=self._registry.get("ProjectDeveloper"),
            architect=self._registry.get("SoftwareArchitect") if "SoftwareArchitect" in roles_set else None,
            security=self._registry.get("SecuritySpecialist") if "SecuritySpecialist" in roles_set else None,
            devops=self._registry.get("DevOpsEngineer") if "DevOpsEngineer" in roles_set else None,
            fe_dev=self._registry.get("FrontendDev") if "FrontendDev" in roles_set else None,
            be_dev=self._registry.get("BackendDev") if "BackendDev" in roles_set else None,
            tester=self._registry.get("Tester") if "Tester" in roles_set else None,
            reporter=self._registry.get("Reporter"),
            compress_phases=getattr(self.config, "compress_phases", False),
        )

        all_outputs: dict[str, str] = {}

        async for event in flow.stream(requirement, plan_context=plan_context):
            yield event
            if event["type"] == "flow_done":
                all_outputs = event.get("outputs", {})

        summary = all_outputs.get(
            "PM_closing",
            all_outputs.get("FinalReport", "Dự án đã hoàn thành."),
        )
        # Build model label for token report
        if getattr(self.config, "multi_model_enabled", False):
            model_label = (
                f"multi-model | claude: {self.config.anthropic_multi_provider} "
                f"| gemini25: {self.config.gemini_reasoning_provider} "
                f"| gemini20: {self.config.gemini_fast_provider}"
            )
        else:
            model_label = self.config.get_active_model() if hasattr(self.config, "get_active_model") else ""
        token_report = self.token_tracker.format_report(model=model_label)
        yield {
            "type": "execution_done",
            "summary": summary,
            "outputs": all_outputs,
            "token_report": token_report,
            "token_summary": self.token_tracker.summary(),
        }

    async def handle_mention(
        self,
        mention: str,
        user_message: str,
        channel_context: str = "",
    ) -> str:
        """Handle a /mention command in a task channel.

        Returns the role's response as a string.
        """
        role = self._registry.get_by_mention(mention)
        if role is None:
            return f"❌ Không tìm thấy role cho lệnh `{mention}`"

        logger.info("handle_mention", mention=mention, role=role.role_name)
        return await role.respond(user_message, context=channel_context)

    async def _pm_summarize(self, requirement: str, outputs: dict[str, str]) -> str:
        pm: ProductManager = self._registry.get("ProductManager")
        outputs_text = "\n\n".join(
            f"### {role}\n{output[:500]}..." if len(output) > 500 else f"### {role}\n{output}"
            for role, output in outputs.items()
        )
        return await pm.respond(
            f"Dự án '{requirement[:60]}' đã hoàn thành.\n\n"
            f"Output từ các roles:\n{outputs_text}\n\n"
            "Hãy viết một summary ngắn (3-5 câu) để báo cáo với user."
        )
