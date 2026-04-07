"""ReAct loop — Reasoning + Acting engine.

Implements the Thought → Action → Observation cycle described in
"ReAct: Synergizing Reasoning and Acting in Language Models" (Yao et al., 2022).

Usage
-----
    loop = ReActLoop(action=llm_action, tools=tools, max_steps=5)
    result = await loop.run(goal=instruction, context=upstream_str)

The loop drives the LLM through repeated Thought/Action/Observation steps until
it emits a `Final Answer:` line or exhausts `max_steps`.  Each step is recorded
in `loop.trajectory` for logging and debugging.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool

from actions.action import LLMAction

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM = """\
You are an autonomous research agent operating in a Thought/Action/Observation loop.

At every step you MUST output exactly one of:
  Thought: <your reasoning about what to do next>
  Action: <tool_name>(<arg>)
  Final Answer: <your final, complete answer>

Rules:
- Always start a step with "Thought:" to reason before acting.
- After a Thought, output "Action:" on the next line, OR "Final Answer:" if done.
- After each Action the system will provide an "Observation:" — wait for it.
- Use "Final Answer:" only when you have enough information to fully answer the goal.
- Never skip Thought. Never emit two Actions in one step.
- If a tool returns empty or unhelpful results, reason about a different query or tool.
"""

STEP_PROMPT = """\
## Goal
{goal}

## Context
{context}

## Available Tools
{tools}

## Trajectory so far
{trajectory}

Continue. Output your next Thought, then either an Action or a Final Answer.
"""

FINAL_ANSWER_PREFIX = "Final Answer:"
THOUGHT_PREFIX = "Thought:"
ACTION_PREFIX = "Action:"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ReActStep:
    thought: str = ""
    action_tool: str = ""
    action_arg: str = ""
    observation: str = ""
    is_final: bool = False
    final_answer: str = ""

    def to_str(self) -> str:
        lines = [f"Thought: {self.thought}"]
        if self.is_final:
            lines.append(f"Final Answer: {self.final_answer}")
        else:
            lines.append(f"Action: {self.action_tool}({self.action_arg})")
            if self.observation:
                lines.append(f"Observation: {self.observation}")
        return "\n".join(lines)


@dataclass
class ReActResult:
    answer: str
    steps: int
    trajectory: list[ReActStep] = field(default_factory=list)
    stopped_by: str = "final_answer"  # "final_answer" | "max_steps" | "error"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class _StepParser:
    """Extracts Thought / Action / Final Answer from raw LLM output."""

    @staticmethod
    def parse(raw: str) -> tuple[str, str, str, bool, str]:
        """Returns (thought, tool_name, tool_arg, is_final, final_answer)."""
        thought = ""
        tool_name = ""
        tool_arg = ""
        is_final = False
        final_answer = ""

        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith(THOUGHT_PREFIX):
                thought = stripped[len(THOUGHT_PREFIX):].strip()
            elif stripped.startswith(FINAL_ANSWER_PREFIX):
                is_final = True
                final_answer = stripped[len(FINAL_ANSWER_PREFIX):].strip()
            elif stripped.startswith(ACTION_PREFIX):
                action_str = stripped[len(ACTION_PREFIX):].strip()
                # Parse "tool_name(arg)" or "tool_name: arg"
                if "(" in action_str and action_str.endswith(")"):
                    tool_name = action_str[: action_str.index("(")]
                    tool_arg = action_str[action_str.index("(") + 1 : -1]
                elif ":" in action_str:
                    parts = action_str.split(":", 1)
                    tool_name = parts[0].strip()
                    tool_arg = parts[1].strip()
                else:
                    tool_name = action_str
                    tool_arg = ""

        return thought, tool_name, tool_arg, is_final, final_answer


# ---------------------------------------------------------------------------
# ReActLoop
# ---------------------------------------------------------------------------

class ReActLoop:
    """Drives a Thought/Action/Observation loop using an LLMAction and a tool list.

    Args:
        action:     An LLMAction with an injected LLM.
        tools:      Available tools the LLM can call.
        max_steps:  Maximum Thought/Action cycles before forcing a final answer.
        system_msg: Optional system message prefix (skill content injected here).
    """

    def __init__(
        self,
        action: LLMAction,
        tools: list[BaseTool],
        max_steps: int = 5,
        system_msg: str = "",
    ) -> None:
        self._action = action
        self._tools: dict[str, BaseTool] = {t.name: t for t in tools}
        self.max_steps = max_steps
        self._system = system_msg or SYSTEM
        self.trajectory: list[ReActStep] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, goal: str, context: str = "") -> ReActResult:
        """Execute the ReAct loop and return a ReActResult."""
        self.trajectory = []
        tool_desc = "\n".join(f"- {n}: {t.description}" for n, t in self._tools.items())

        for step_num in range(1, self.max_steps + 1):
            trajectory_str = self._format_trajectory()
            prompt = STEP_PROMPT.format(
                goal=goal,
                context=context or "(none)",
                tools=tool_desc or "(none)",
                trajectory=trajectory_str or "(none yet — this is step 1)",
            )

            raw = await self._action.aask(prompt, system_msg=self._system)
            thought, tool_name, tool_arg, is_final, final_answer = _StepParser.parse(raw)

            step = ReActStep(thought=thought, is_final=is_final, final_answer=final_answer)

            if is_final:
                # Guard: require at least one tool call before accepting a final answer.
                # If the LLM jumps straight to Final Answer without searching, treat it
                # as a missing Action and continue the loop so it is forced to use a tool.
                has_actions = any(s.action_tool for s in self.trajectory)
                if not has_actions and self._tools:
                    # Inject a corrective observation and continue
                    corrective = ReActStep(
                        thought=thought,
                        action_tool="",
                        action_arg="",
                        observation=(
                            "[System] You must call at least one tool before answering. "
                            "Please issue an Action now."
                        ),
                        is_final=False,
                    )
                    self.trajectory.append(corrective)
                    continue
                self.trajectory.append(step)
                return ReActResult(
                    answer=final_answer,
                    steps=step_num,
                    trajectory=list(self.trajectory),
                    stopped_by="final_answer",
                )

            # Execute the action
            observation = await self._execute_tool(tool_name, tool_arg, goal)
            step.action_tool = tool_name
            step.action_arg = tool_arg
            step.observation = observation
            self.trajectory.append(step)

        # Exhausted max_steps — force a final answer from whatever we have
        final = await self._force_final(goal, context, tool_desc)
        return ReActResult(
            answer=final,
            steps=self.max_steps,
            trajectory=list(self.trajectory),
            stopped_by="max_steps",
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _execute_tool(self, tool_name: str, tool_arg: str, fallback_query: str) -> str:
        tool = self._tools.get(tool_name)
        if tool is None:
            available = ", ".join(self._tools.keys())
            return f"[Error] Tool '{tool_name}' not found. Available: {available}"
        try:
            arg = self._clean_tool_arg(tool_arg or fallback_query)
            result = await tool.arun(arg)
            return str(result)
        except Exception as e:
            return f"[Error] Tool '{tool_name}' raised: {e}"

    @staticmethod
    def _clean_tool_arg(arg: str) -> str:
        """Strip common LLM formatting artifacts from tool arguments.

        LLMs sometimes wrap arguments as ``query="..."`` or ``query='...'``
        instead of passing the bare string.  This normalises those cases.
        """
        arg = arg.strip()
        # Handle: query="some text" or query='some text'
        for prefix in ("query=", "query ="):
            if arg.lower().startswith(prefix):
                arg = arg[len(prefix):].strip()
                break
        # Strip surrounding quotes if present
        if len(arg) >= 2 and arg[0] in ('"', "'") and arg[-1] == arg[0]:
            arg = arg[1:-1]
        return arg

    async def _force_final(self, goal: str, context: str, tool_desc: str) -> str:
        """Ask LLM to synthesise a final answer from accumulated trajectory."""
        trajectory_str = self._format_trajectory()
        prompt = (
            f"## Goal\n{goal}\n\n"
            f"## Context\n{context or '(none)'}\n\n"
            f"## Trajectory\n{trajectory_str}\n\n"
            "You have reached the step limit. "
            "Based on everything above, write your best Final Answer now."
        )
        raw = await self._action.aask(prompt, system_msg=self._system)
        _, _, _, _, final = _StepParser.parse(raw)
        return final or raw.strip()

    def _format_trajectory(self) -> str:
        return "\n\n".join(s.to_str() for s in self.trajectory)

    # ------------------------------------------------------------------
    # Introspection helpers (useful for logging / tests)
    # ------------------------------------------------------------------

    def observations(self) -> list[str]:
        return [s.observation for s in self.trajectory if s.observation]

    def thoughts(self) -> list[str]:
        return [s.thought for s in self.trajectory if s.thought]

    def actions_taken(self) -> list[tuple[str, str]]:
        return [(s.action_tool, s.action_arg) for s in self.trajectory if s.action_tool]
