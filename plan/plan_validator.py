from __future__ import annotations

from plan.model import Plan
from plan.plan_parser import precheck_update_plan_from_rsp

# Minimum character length for a search task instruction to be considered specific enough.
_MIN_SEARCH_INSTRUCTION_LEN = 40

# Keywords that indicate a well-formed search instruction (at least one required).
_SEARCH_QUALITY_KEYWORDS = ("search:", "scope:", "need to know:", "find:", "look up:")


class PlanValidator:
    """Validates a raw LLM plan response against an existing Plan. Single responsibility."""

    def validate(self, rsp: str, current_plan: Plan) -> tuple[bool, str]:
        """Return (is_valid, error_message).

        Runs two layers of checks:
        1. Structural — can the JSON be parsed into a valid Plan?
        2. Semantic — do the tasks follow quality rules?
        """
        is_valid, error = precheck_update_plan_from_rsp(rsp, current_plan)
        if not is_valid:
            return False, error

        # Parse tasks from the response to run semantic checks
        import json
        try:
            tasks = json.loads(rsp)
        except Exception:
            return False, "Plan JSON could not be parsed for semantic validation."

        return self._semantic_checks(tasks)

    # ------------------------------------------------------------------
    # Semantic checks
    # ------------------------------------------------------------------

    def _semantic_checks(self, tasks: list[dict]) -> tuple[bool, str]:
        """Apply quality rules to the list of task dicts."""
        task_ids = {t.get("task_id", "") for t in tasks}
        task_types = {t.get("task_id", ""): t.get("task_type", "") for t in tasks}

        # Rule 1: if a report task exists, a validate task must depend on it
        report_ids = {tid for tid, ttype in task_types.items() if ttype == "report"}
        validate_tasks = [t for t in tasks if t.get("task_type") == "validate"]

        if report_ids:
            validated_reports = set()
            for vt in validate_tasks:
                for dep in vt.get("dependent_task_ids", []):
                    if dep in report_ids:
                        validated_reports.add(dep)
            missing = report_ids - validated_reports
            if missing:
                return (
                    False,
                    f"Plan has report task(s) {missing} but no validate task depending on them. "
                    "Add a 'validate' task that depends on each report task.",
                )

        # Rule 2: search task instructions must be specific enough
        for t in tasks:
            if t.get("task_type") != "search":
                continue
            instruction = t.get("instruction", "")
            if len(instruction) < _MIN_SEARCH_INSTRUCTION_LEN:
                return (
                    False,
                    f"Search task '{t.get('task_id')}' instruction is too vague "
                    f"(length {len(instruction)} < {_MIN_SEARCH_INSTRUCTION_LEN} chars). "
                    "Use format: 'Search: [topic]\\nScope: [scope]\\nNeed to know: [question]'.",
                )
            instruction_lower = instruction.lower()
            has_keyword = any(kw in instruction_lower for kw in _SEARCH_QUALITY_KEYWORDS)
            if not has_keyword:
                return (
                    False,
                    f"Search task '{t.get('task_id')}' instruction is missing structure keywords. "
                    "Include at least one of: Search:, Scope:, Need to know:, Find:, Look up:.",
                )

        return True, ""
