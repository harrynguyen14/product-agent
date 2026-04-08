from __future__ import annotations


def extract_content(response) -> str:
    """Extract text content from a LangChain response object."""
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "\n".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return content
