import asyncio
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

import typer
from rich.console import Console
from rich.table import Table

from config.settings import AppConfig
from config.provider_config import LLMProvider
from infrastructure.logging import setup_logging

app = typer.Typer(
    name="mard",
    help="Multi-Agent Telegram Bot System",
    add_completion=False,
)
console = Console()


@app.command()
def telegram(
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p",
        help="LLM provider: anthropic | openai | gemini | ollama | lmstudio",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Model name override",
    ),
    max_retries: int = typer.Option(3, "--max-retries", help="Max retries mỗi role"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    log_format: str = typer.Option("console", "--log-format", help="console | json"),
):
    """Start tất cả role bot. Bot nào có token trong .env thì chạy, không có thì skip."""
    from config.settings import ALL_ROLES
    from telegram_bot.bot import run_all_bots

    setup_logging(level=log_level, fmt=log_format)

    config_kwargs: dict = {
        "max_retries": max_retries,
        "log_level": log_level,
        "log_format": log_format,
    }
    if provider:
        try:
            config_kwargs["llm_provider"] = LLMProvider(provider)
        except ValueError:
            console.print(f"[red]Invalid provider: {provider}[/red]")
            raise typer.Exit(1)

    base_config = AppConfig(**config_kwargs)

    if model:
        p = base_config.llm_provider
        field_map = {
            LLMProvider.ANTHROPIC: "anthropic_provider",
            LLMProvider.OPENAI:    "openai_provider",
            LLMProvider.GEMINI:    "gemini_provider",
            LLMProvider.OLLAMA:    "ollama_provider",
            LLMProvider.LMSTUDIO:  "lmstudio_provider",
        }
        if p in field_map:
            base_config = base_config.model_copy(update={field_map[p]: model})

    active_roles = [r for r in ALL_ROLES if base_config.get_token(r)]
    if not active_roles:
        console.print(
            "[red]Không có bot nào có token.[/red]\n"
            "Set [bold]MA_TOKEN_<ROLE>[/bold] trong .env cho các role cần chạy.\n"
            "Ví dụ: MA_TOKEN_PM=... MA_TOKEN_BA=..."
        )
        raise typer.Exit(1)

    console.print(
        f"[bold green]Khởi động {len(active_roles)} bot[/bold green]: "
        + ", ".join(f"[cyan]{r}[/cyan]" for r in active_roles) + "\n"
        f"Provider: [cyan]{base_config.llm_provider.value}[/cyan]  "
        f"Model: [cyan]{base_config.get_active_model()}[/cyan]\n"
        "[dim]Press Ctrl+C to stop.[/dim]"
    )

    asyncio.run(run_all_bots(base_config, active_roles))


@app.command()
def providers():
    """Liệt kê các LLM provider được hỗ trợ."""
    table = Table(title="Supported LLM Providers", show_header=True, header_style="bold cyan")
    table.add_column("Provider", style="bold")
    table.add_column("Env Var (MA_ prefix)")
    table.add_column("Default Model")
    table.add_column("Notes")

    table.add_row("anthropic", "MA_ANTHROPIC_API_KEY", "claude-opus-4-6",   "Requires API key")
    table.add_row("openai",    "MA_OPENAI_API_KEY",    "gpt-4o",            "Requires API key")
    table.add_row("gemini",    "MA_GEMINI_API_KEY",    "gemini-2.0-flash",  "Requires API key")
    table.add_row("ollama",    "(none)",                "llama3.2",          "Local — run: ollama serve")
    table.add_row("lmstudio",  "(none)",                "local-model",       "Local — LM Studio server on :1234")

    console.print(table)


if __name__ == "__main__":
    app()
