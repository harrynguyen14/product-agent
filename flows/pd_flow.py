from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Optional

from infrastructure.logging import get_logger
from roles.software_architect import SoftwareArchitect
from roles.security_specialist import SecuritySpecialist
from roles.devops_engineer import DevOpsEngineer
from roles.frontend_dev import FrontendDev
from roles.backend_dev import BackendDev
from roles.tester import Tester

logger = get_logger("pd_flow")


class PDFlow:
    """Product Development flow executed in a task channel.

    Flow (with parallelism where possible):
        SoftwareArchitect  ← first, sets the foundation
              ↓
        SecuritySpecialist + DevOpsEngineer  ← parallel (both need arch)
              ↓
        FrontendDev + BackendDev  ← parallel (both need arch + security)
              ↓
        Tester  ← last, needs all outputs

    Only roles that are active (not None) are executed.
    """

    def __init__(
        self,
        architect: Optional[SoftwareArchitect] = None,
        security: Optional[SecuritySpecialist] = None,
        devops: Optional[DevOpsEngineer] = None,
        fe_dev: Optional[FrontendDev] = None,
        be_dev: Optional[BackendDev] = None,
        tester: Optional[Tester] = None,
    ) -> None:
        self._arch = architect
        self._security = security
        self._devops = devops
        self._fe = fe_dev
        self._be = be_dev
        self._tester = tester

    async def run(
        self,
        requirement: str,
        ba_context: str = "",
        plan_context: str = "",
    ) -> dict[str, str]:
        """Execute the PD flow. Returns outputs keyed by role_name."""
        outputs: dict[str, str] = {}
        context_base = self._build_base_context(requirement, ba_context, plan_context)

        # --- Phase 1: Architecture ---
        if self._arch:
            logger.info("pd_flow_arch_start")
            arch_output = await self._arch.run_task(
                f"{context_base}\nHãy thiết kế kiến trúc hệ thống tổng thể."
            )
            outputs["SoftwareArchitect"] = arch_output
            logger.info("pd_flow_arch_done")
        else:
            arch_output = ""

        arch_ctx = f"\n\n## Kiến trúc hệ thống\n{arch_output}" if arch_output else ""

        # --- Phase 2: Security + DevOps (parallel) ---
        phase2_coros = []
        phase2_keys = []

        if self._security:
            phase2_coros.append(
                self._security.run_task(
                    f"{context_base}{arch_ctx}\nHãy thực hiện security review và threat modeling."
                )
            )
            phase2_keys.append("SecuritySpecialist")

        if self._devops:
            phase2_coros.append(
                self._devops.run_task(
                    f"{context_base}{arch_ctx}\nHãy thiết kế CI/CD pipeline và infrastructure."
                )
            )
            phase2_keys.append("DevOpsEngineer")

        if phase2_coros:
            logger.info("pd_flow_phase2_start", roles=phase2_keys)
            results = await asyncio.gather(*phase2_coros)
            for key, result in zip(phase2_keys, results):
                outputs[key] = result
            logger.info("pd_flow_phase2_done")

        security_ctx = f"\n\n## Security Review\n{outputs.get('SecuritySpecialist', '')}" if "SecuritySpecialist" in outputs else ""

        # --- Phase 3: FE + BE (parallel) ---
        phase3_coros = []
        phase3_keys = []

        if self._fe:
            phase3_coros.append(
                self._fe.run_task(
                    f"{context_base}{arch_ctx}{security_ctx}\n"
                    "Hãy implement frontend theo design spec và kiến trúc đã định."
                )
            )
            phase3_keys.append("FrontendDev")

        if self._be:
            phase3_coros.append(
                self._be.run_task(
                    f"{context_base}{arch_ctx}{security_ctx}\n"
                    "Hãy implement backend API và database theo kiến trúc đã định."
                )
            )
            phase3_keys.append("BackendDev")

        if phase3_coros:
            logger.info("pd_flow_phase3_start", roles=phase3_keys)
            results = await asyncio.gather(*phase3_coros)
            for key, result in zip(phase3_keys, results):
                outputs[key] = result
            logger.info("pd_flow_phase3_done")

        # --- Phase 4: Testing ---
        if self._tester:
            logger.info("pd_flow_tester_start")
            all_impl = "\n\n".join(
                f"## {k}\n{v}" for k, v in outputs.items()
            )
            tester_output = await self._tester.run_task(
                f"{context_base}\n\n## Toàn bộ implementation\n{all_impl}\n\n"
                "Hãy lập test plan và viết test cases toàn diện."
            )
            outputs["Tester"] = tester_output
            logger.info("pd_flow_tester_done")

        return outputs

    async def stream(
        self,
        requirement: str,
        ba_context: str = "",
        plan_context: str = "",
    ) -> AsyncGenerator[dict, None]:
        """Stream events as each phase completes."""
        outputs: dict[str, str] = {}
        context_base = self._build_base_context(requirement, ba_context, plan_context)

        # Phase 1: Architecture
        if self._arch:
            yield {"type": "role_start", "role": "SoftwareArchitect"}
            arch_output = await self._arch.run_task(
                f"{context_base}\nHãy thiết kế kiến trúc hệ thống tổng thể."
            )
            outputs["SoftwareArchitect"] = arch_output
            yield {"type": "role_done", "role": "SoftwareArchitect", "output": arch_output}
        else:
            arch_output = ""

        arch_ctx = f"\n\n## Kiến trúc hệ thống\n{arch_output}" if arch_output else ""

        # Phase 2: Security + DevOps (parallel)
        phase2_coros = []
        phase2_keys = []
        if self._security:
            phase2_coros.append(
                self._security.run_task(f"{context_base}{arch_ctx}\nSecurity review và threat modeling.")
            )
            phase2_keys.append("SecuritySpecialist")
            yield {"type": "role_start", "role": "SecuritySpecialist"}
        if self._devops:
            phase2_coros.append(
                self._devops.run_task(f"{context_base}{arch_ctx}\nCI/CD pipeline và infrastructure.")
            )
            phase2_keys.append("DevOpsEngineer")
            yield {"type": "role_start", "role": "DevOpsEngineer"}

        if phase2_coros:
            results = await asyncio.gather(*phase2_coros)
            for key, result in zip(phase2_keys, results):
                outputs[key] = result
                yield {"type": "role_done", "role": key, "output": result}

        security_ctx = f"\n\n## Security Review\n{outputs.get('SecuritySpecialist', '')}" if "SecuritySpecialist" in outputs else ""

        # Phase 3: FE + BE (parallel)
        phase3_coros = []
        phase3_keys = []
        if self._fe:
            phase3_coros.append(
                self._fe.run_task(f"{context_base}{arch_ctx}{security_ctx}\nImplement frontend.")
            )
            phase3_keys.append("FrontendDev")
            yield {"type": "role_start", "role": "FrontendDev"}
        if self._be:
            phase3_coros.append(
                self._be.run_task(f"{context_base}{arch_ctx}{security_ctx}\nImplement backend API.")
            )
            phase3_keys.append("BackendDev")
            yield {"type": "role_start", "role": "BackendDev"}

        if phase3_coros:
            results = await asyncio.gather(*phase3_coros)
            for key, result in zip(phase3_keys, results):
                outputs[key] = result
                yield {"type": "role_done", "role": key, "output": result}

        # Phase 4: Tester
        if self._tester:
            yield {"type": "role_start", "role": "Tester"}
            all_impl = "\n\n".join(f"## {k}\n{v}" for k, v in outputs.items())
            tester_output = await self._tester.run_task(
                f"{context_base}\n\n## Implementation\n{all_impl}\n\nLập test plan và test cases."
            )
            outputs["Tester"] = tester_output
            yield {"type": "role_done", "role": "Tester", "output": tester_output}

        yield {"type": "flow_done", "flow": "pd_flow", "outputs": outputs}

    @staticmethod
    def _build_base_context(requirement: str, ba_context: str, plan_context: str) -> str:
        parts = [f"## Yêu cầu dự án\n{requirement}"]
        if plan_context:
            parts.append(f"## Kế hoạch\n{plan_context}")
        if ba_context:
            parts.append(f"## Phân tích nghiệp vụ\n{ba_context}")
        return "\n\n".join(parts)
