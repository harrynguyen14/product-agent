---
name: api-docs-lookup
description: API documentation lookup guide. Use when writing code that calls an external library or API — instructs the agent to load pre-integrated API docs via load_api_doc() instead of relying on training knowledge, which may be outdated.
---

# API Documentation Skill

When writing code that uses an external library or API, always prioritize loading the official documentation rather than relying on trained knowledge. Docs may have been updated with new APIs, new models, or changed syntax.

## Pre-integrated Libraries

The following docs are available — call `load_api_doc("<name>")` to retrieve content:

| Library | Key | Use when |
|---|---|---|
| Anthropic Claude API | `anthropic` | Calling Claude, building AI agents |
| OpenAI API | `openai` | Calling GPT, embeddings, vision |
| FastAPI | `fastapi` | Building REST API endpoints |
| Pydantic | `pydantic` | Data validation, schemas |
| Pydantic Settings | `pydantic_settings` | App configuration, env vars |
| Discord.py | `discord` | Discord bot, webhooks |
| structlog | `structlog` | Structured logging |
| Typer | `typer` | CLI applications |
| aiohttp | `aiohttp` | Async HTTP client/server |
| Rich | `rich` | Terminal formatting, output |
| python-dotenv | `python_dotenv` | Load .env files |

## Usage in Code

```python
from skills.loader import load_api_doc

anthropic_doc = load_api_doc("anthropic")
fastapi_doc = load_api_doc("fastapi")
```

## Priority Rules When Writing Code

1. **Anthropic SDK** — Always call `load_api_doc("anthropic")` when writing code that invokes Claude.
   - Default models (2026): `claude-sonnet-4-6-20250827` (general), `claude-opus-4-6-20250826` (high-performance), `claude-haiku-4-5-20251001` (fast)
   - Import: `from anthropic import Anthropic` or `from anthropic import AsyncAnthropic`

2. **FastAPI** — Use `load_api_doc("fastapi")` when creating endpoints, middleware, or dependency injection.

3. **Pydantic** — Use `load_api_doc("pydantic")` for schema validation. Use `pydantic_settings` for config.

4. **Discord** — Use `load_api_doc("discord")` when working with Discord bot events, webhooks, slash commands.

5. **Structlog** — Use `load_api_doc("structlog")` for structured logging. Do not use `print()` or plain `logging`.

## When the Library Is Not Pre-integrated

If a library is not in the list above, use web search to find the latest docs:

```
"<library-name> python documentation site:docs.<library>.io"
"<library-name> python api reference 2025"
```

Always verify the version in `requirements.txt` or `pyproject.toml` before looking up docs.

## Note on Model Names

When working with LLMs, always check the current model ID in `config/settings.py` or `.env`. Never hardcode model names — use the value from `AppConfig`.
