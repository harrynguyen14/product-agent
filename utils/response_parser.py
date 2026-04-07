from __future__ import annotations

import re


class ResponseParser:
    @classmethod
    def parse_json(cls, text: str) -> str:
        """Extract JSON content from a markdown code block, or return text as-is."""
        pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        stripped = text.strip()
        if stripped.startswith(("{", "[")):
            return stripped
        return stripped

    @classmethod
    def parse_code(cls, text: str, lang: str = "") -> str:
        """Extract code content from a markdown code block of the given language."""
        pattern = rf"```{lang}\s*\n(.*?)\n```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()
