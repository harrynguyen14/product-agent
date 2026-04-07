from __future__ import annotations

import json

from actions.action import ActionContext, LLMAction
from utils.response_parser import ResponseParser


GENERATE_QUESTIONS_PROMPT = """\
## User Request
{user_input}

## Task
You are a research planning assistant. Given the user request above, identify what specific information is needed to build a thorough research plan.

Generate a list of sub-questions that must be answered before writing the plan. Each question should target a distinct aspect (scope, constraints, output format, depth, sources, etc.).

Output a JSON list of strings:
```json
["question 1", "question 2", "question 3"]
```
"""

ANSWER_QUESTIONS_PROMPT = """\
## User Request
{user_input}

## Sub-questions to clarify
{questions}

## Task
Answer each sub-question above based on the user request and your knowledge. Be concise and specific.

Output a JSON object mapping each question to its answer:
```json
{{
  "question 1": "answer 1",
  "question 2": "answer 2"
}}
```
"""


class Clarify(LLMAction):
    async def run(self, ctx: ActionContext) -> str:
        user_input = ctx.get("input", "")
        if isinstance(user_input, list):
            user_input = "\n".join(str(x) for x in user_input)

        questions_raw = await self.aask(
            GENERATE_QUESTIONS_PROMPT.format(user_input=user_input)
        )
        questions_json = ResponseParser.parse_json(questions_raw)
        try:
            questions: list[str] = json.loads(questions_json)
            if not isinstance(questions, list):
                questions = [questions_json]
        except json.JSONDecodeError:
            questions = [questions_json]

        answers_raw = await self.aask(
            ANSWER_QUESTIONS_PROMPT.format(
                user_input=user_input,
                questions="\n".join(f"- {q}" for q in questions),
            )
        )
        answers_json = ResponseParser.parse_json(answers_raw)
        try:
            answers: dict[str, str] = json.loads(answers_json)
            if not isinstance(answers, dict):
                answers = {}
        except json.JSONDecodeError:
            answers = {q: answers_json for q in questions[:1]}

        qa_lines = "\n".join(f"Q: {q}\nA: {a}" for q, a in answers.items())
        return f"## User Request\n{user_input}\n\n## Clarifications\n{qa_lines}"
