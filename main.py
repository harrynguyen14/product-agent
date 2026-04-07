import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from config.settings import AppConfig, get_config
from config.provider_config import LLMProvider
from core.runner import EnvironmentRunner
from infrastructure.logging import setup_logging

app = typer.Typer(
    name="mard",
    help="Multi-Agent R&D System powered by MetaGPT-style Role/Message architecture",
    add_completion=False,
)
console = Console()


@app.command()
def run(
    problem: str = typer.Argument(..., help="The R&D problem to investigate"),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p",
        help="LLM provider: anthropic | openai | gemini | ollama | lmstudio",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Model name override (e.g. gpt-4o, llama3.2, claude-opus-4-6)",
    ),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream output"),
    writing: bool = typer.Option(True, "--writing/--no-writing", help="Include writing agent"),
    max_retries: int = typer.Option(3, "--max-retries", help="Max validation retries per task"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save final state to JSON file"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    log_format: str = typer.Option("console", "--log-format", help="console | json"),
    mcp_config: Optional[Path] = typer.Option(
        None, "--mcp-config",
        help="Path to MCP servers JSON config file",
    ),
    enable_mcp: bool = typer.Option(False, "--mcp/--no-mcp", help="Enable MCP tool servers"),
    enable_skills: bool = typer.Option(False, "--skills/--no-skills", help="Enable registered skills"),
    skill_names: Optional[str] = typer.Option(
        None, "--skill-names",
        help="Comma-separated skill names to bind (default: all registered)",
    ),
):
    setup_logging(level=log_level, fmt=log_format)

    parsed_skill_names: Optional[list[str]] = None
    if skill_names:
        parsed_skill_names = [s.strip() for s in skill_names.split(",") if s.strip()]

    config_kwargs = {
        "needs_writing": writing,
        "max_retries": max_retries,
        "log_level": log_level,
        "log_format": log_format,
        "streaming_enabled": stream,
        "mcp_enabled": enable_mcp,
        "skills_enabled": enable_skills,
    }
    if mcp_config:
        config_kwargs["mcp_config_file"] = str(mcp_config)
    if parsed_skill_names:
        config_kwargs["skill_names"] = parsed_skill_names

    if provider:
        try:
            config_kwargs["llm_provider"] = LLMProvider(provider)
        except ValueError:
            console.print(f"[red]Invalid provider: {provider}. Use: anthropic | openai | gemini | ollama | lmstudio[/red]")
            raise typer.Exit(1)

    config = AppConfig(**config_kwargs)

    if model:
        p = config.llm_provider
        field_map = {
            LLMProvider.ANTHROPIC: "anthropic_provider",
            LLMProvider.OPENAI:    "openai_provider",
            LLMProvider.GEMINI:    "gemini_provider",
            LLMProvider.OLLAMA:    "ollama_provider",
            LLMProvider.LMSTUDIO:  "lmstudio_provider",
        }
        if p in field_map:
            config = config.model_copy(update={field_map[p]: model})

    _print_run_info(config, problem)

    runner = EnvironmentRunner(config=config)

    console.print("[cyan]Running pipeline...[/cyan]")
    final_state = asyncio.run(runner.run(problem))
    _print_final_state(final_state, console)

    if output:
        _save_output(final_state, output, console)


@app.command()
def providers():
    table = Table(title="Supported LLM Providers", show_header=True, header_style="bold cyan")
    table.add_column("Provider", style="bold")
    table.add_column("Env Var")
    table.add_column("Default Model")
    table.add_column("Notes")

    table.add_row("anthropic", "MARD_ANTHROPIC_API_KEY", "claude-opus-4-6",    "Requires API key")
    table.add_row("openai",    "MARD_OPENAI_API_KEY",    "gpt-4o",             "Requires API key")
    table.add_row("gemini",    "MARD_GEMINI_API_KEY",    "gemini-2.0-flash",   "Requires API key")
    table.add_row("ollama",    "(none)",                  "llama3.2",           "Local — run: ollama serve")
    table.add_row("lmstudio",  "(none)",                  "local-model",        "Local — LM Studio server on :1234")

    console.print(table)
    console.print("\n[dim]Set MARD_LLM_PROVIDER=<provider> in .env to change default[/dim]")


@app.command()
def skills():
    from tools.registry import build_default_registry
    registry = build_default_registry()
    all_tools = registry.all_tools()
    if not all_tools:
        console.print("[yellow]No tools registered.[/yellow]")
        return
    table = Table(title="Registered Tools / Skills", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    for t in all_tools:
        table.add_row(t.name, t.description or "")
    console.print(table)


@app.command()
def example():
    env_example = Path(".env.example")
    if env_example.exists():
        content = env_example.read_text()
        console.print(Syntax(content, "bash", theme="monokai"))
    else:
        console.print("[yellow]No .env.example found. Copy from the project root.[/yellow]")


def _print_run_info(config: AppConfig, problem: str) -> None:
    provider = config.llm_provider.value
    model = config.get_active_model() if hasattr(config, "get_active_model") else provider
    extras = []
    if config.mcp_enabled:
        extras.append(f"MCP: {config.mcp_config_file or 'inline'}")
    if config.skills_enabled:
        names = ", ".join(config.skill_names) if config.skill_names else "all"
        extras.append(f"Skills: {names}")
    extras_line = ("  " + "  ".join(extras)) if extras else ""
    console.print(Panel(
        f"[bold cyan]Problem:[/bold cyan] {problem}\n"
        f"[bold]Provider:[/bold] {provider}  [bold]Model:[/bold] {model}\n"
        f"[bold]Writing:[/bold] {config.needs_writing}  "
        f"[bold]Max retries:[/bold] {config.max_retries}{extras_line}",
        title="[bold]Multi-Agent R&D System[/bold]",
        expand=False,
    ))


def _print_final_state(state: dict, con: Console) -> None:
    assign = state.get("assign_output")
    if assign and hasattr(assign, "tasks"):
        table = Table(title="Assigned R&D Tasks", show_header=True, header_style="bold green")
        table.add_column("#", width=3)
        table.add_column("Title")
        table.add_column("Owner")
        table.add_column("Priority")
        for i, task in enumerate(assign.tasks, 1):
            p = task.priority if isinstance(task.priority, str) else task.priority.value
            table.add_row(str(i), task.title, task.owner_role, p)
        con.print(table)

    report = state.get("report_output")
    if report and isinstance(report, str):
        con.print(Panel(report[:500], title="Research Report", expand=False))
    elif report and hasattr(report, "title"):
        con.print(Panel(
            f"[bold]{report.title}[/bold]\n\n{getattr(report, 'executive_summary', '')}",
            title="Research Report Summary",
            expand=False,
        ))


def _save_output(state: dict, path: Path, con: Console) -> None:
    def _serialize(obj):
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if isinstance(obj, list):
            return [_serialize(i) for i in obj]
        return obj

    serializable = {k: _serialize(v) for k, v in state.items()}
    path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2))
    con.print(f"\n[green]Output saved to:[/green] {path}")


@app.command()
def discord(
    token: Optional[str] = typer.Option(
        None, "--token", "-t",
        help="Discord Bot Token (overrides MA_DISCORD_BOT_TOKEN env var)",
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p",
        help="LLM provider: anthropic | openai | gemini | ollama | lmstudio",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Model name override",
    ),
    max_retries: int = typer.Option(3, "--max-retries", help="Max plan retries"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    log_format: str = typer.Option("console", "--log-format", help="console | json"),
):
    """Start the Discord multi-agent bot."""
    import os
    from discord_bot.bot import run_bot

    setup_logging(level=log_level, fmt=log_format)

    config_kwargs = {
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

    config = AppConfig(**config_kwargs)

    bot_token = token or config.discord_bot_token or os.environ.get("MA_DISCORD_BOT_TOKEN", "")
    if not bot_token:
        console.print(
            "[red]No Discord bot token found.[/red]\n"
            "Set [bold]MA_DISCORD_BOT_TOKEN[/bold] in .env or pass --token <token>.\n"
            "Create a bot at https://discord.com/developers/applications"
        )
        raise typer.Exit(1)

    if model:
        p = config.llm_provider
        field_map = {
            LLMProvider.ANTHROPIC: "anthropic_provider",
            LLMProvider.OPENAI:    "openai_provider",
            LLMProvider.GEMINI:    "gemini_provider",
            LLMProvider.OLLAMA:    "ollama_provider",
            LLMProvider.LMSTUDIO:  "lmstudio_provider",
        }
        if p in field_map:
            config = config.model_copy(update={field_map[p]: model})

    console.print(
        f"[bold green]Discord bot starting[/bold green] — "
        f"provider: [cyan]{config.llm_provider.value}[/cyan], "
        f"model: [cyan]{config.get_active_model()}[/cyan]\n"
        "[dim]Press Ctrl+C to stop.[/dim]"
    )
    run_bot(bot_token, config)


@app.command()
def telegram(
    token: Optional[str] = typer.Option(
        None, "--token", "-t",
        help="Telegram Bot Token (overrides TELEGRAM_BOT_TOKEN env var)",
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p",
        help="LLM provider: anthropic | openai | gemini | ollama | lmstudio",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Model name override",
    ),
    writing: bool = typer.Option(True, "--writing/--no-writing", help="Include report generation"),
    max_retries: int = typer.Option(3, "--max-retries", help="Max validation retries per task"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    log_format: str = typer.Option("console", "--log-format", help="console | json"),
):
    import os
    from telegram_bot.bot import run_bot

    setup_logging(level=log_level, fmt=log_format)

    config_kwargs = {
        "needs_writing": writing,
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

    config = AppConfig(**config_kwargs)

    bot_token = token or config.telegram_bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        console.print(
            "[red]No Telegram bot token found.[/red]\n"
            "Set [bold]MARD_TELEGRAM_BOT_TOKEN[/bold] in .env or pass --token <token>.\n"
            "Get a token from @BotFather on Telegram."
        )
        raise typer.Exit(1)

    if model:
        p = config.llm_provider
        field_map = {
            LLMProvider.ANTHROPIC: "anthropic_provider",
            LLMProvider.OPENAI:    "openai_provider",
            LLMProvider.GEMINI:    "gemini_provider",
            LLMProvider.OLLAMA:    "ollama_provider",
            LLMProvider.LMSTUDIO:  "lmstudio_provider",
        }
        if p in field_map:
            config = config.model_copy(update={field_map[p]: model})

    console.print(
        f"[bold green]Telegram bot starting[/bold green] — "
        f"provider: [cyan]{config.llm_provider.value}[/cyan], "
        f"model: [cyan]{config.get_active_model()}[/cyan]\n"
        "[dim]Press Ctrl+C to stop.[/dim]"
    )
    run_bot(bot_token, config)


if __name__ == "__main__":
    app()
