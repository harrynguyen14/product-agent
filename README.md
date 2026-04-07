# Product Multi-Agent System

A multi-agent product development system where specialized AI roles collaborate to turn a requirement into a full product spec — orchestrated by a Product Manager and delivered via Discord or Telegram.

## How It Works

User sends a requirement → PM plans with Planner → team executes in phases:

```
Phase 1: Business Analysis    PM → BusinessAnalyst → PM review
Phase 2: UI/UX Design         PM → UIUXDesigner → PM review
Phase 3: Development          PM → ProjectDeveloper → [Architect → Security/DevOps → FE/BE → Tester]
Phase 4: Final Report         PM → Reporter → PM review → delivered to user
```

Each role runs as a separate agent with its own Discord webhook identity (avatar + username).

---

## Project Structure

```
product-multi-agent/
├── main.py                     # CLI entrypoint (discord / telegram / run / providers)
├── dev.py                      # Hot-reload runner for development (watches .py files)
├── pyproject.toml
├── requirements.txt
│
├── config/
│   ├── settings.py             # AppConfig (pydantic-settings, env prefix MA_)
│   ├── provider_config.py      # LLMProvider enum + per-provider model/key fields
│   └── optional/               # Optional feature configs
│
├── core/
│   ├── runner.py               # EnvironmentRunner — CLI pipeline entrypoint
│   ├── discord_runner.py       # DiscordEnvironmentRunner — Discord flow orchestrator
│   └── llm_factory.py          # Builds LangChain LLM from AppConfig
│
├── flows/
│   ├── product_flow.py         # ProductFlow — full PM-orchestrated flow (Phases 1-4)
│   ├── ba_flow.py              # BAFlow — Business Analysis + UI/UX standalone flow
│   ├── pd_flow.py              # PDFlow — Development team standalone flow
│   └── planning_flow.py        # PlanningFlow — PM + Planner → plan → user review
│
├── roles/
│   ├── base_role.py            # BaseRole — base class with LLM, memory, run_task()
│   ├── registry.py             # RoleRegistry — instantiates and caches role instances
│   ├── product_manager.py      # PM — orchestrator, assigns tasks, reviews outputs
│   ├── business_analyst.py     # BA — functional specs, user stories, AC
│   ├── ui_ux_designer.py       # UIUXDesigner — wireframes, design system, UX notes
│   ├── project_developer.py    # ProjectDeveloper — dev team coordinator
│   ├── software_architect.py   # SoftwareArchitect — system design, DB schema
│   ├── backend_dev.py          # BackendDev — API, database implementation
│   ├── frontend_dev.py         # FrontendDev — UI implementation
│   ├── security_specialist.py  # SecuritySpecialist — threat modeling, RLS review
│   ├── devops_engineer.py      # DevOpsEngineer — CI/CD, infrastructure
│   ├── tester.py               # Tester — test plans, test cases
│   ├── reporter.py             # Reporter — final report writing
│   └── planner.py              # Planner — breaks requirement into task list
│
├── discord_bot/
│   ├── bot.py                  # Discord bot — event handlers, slash commands
│   ├── channel_manager.py      # Creates/manages task channels per requirement
│   ├── webhook_manager.py      # Per-agent webhook identity (username + avatar)
│   ├── formatters.py           # Message formatting helpers
│   └── review_gate.py          # Pauses flow to wait for user approval in Discord
│
├── telegram_bot/
│   ├── bot.py                  # Telegram bot — message handlers
│   ├── formatters.py           # Telegram-specific formatting
│   └── review_gate.py          # User approval gate for Telegram
│
├── skills/
│   ├── loader.py               # Loads .md skill files and injects into role prompts
│   ├── pm_skill.md             # PM orchestration instructions
│   ├── ba_skill.md             # BA analysis instructions
│   ├── architect_skill.md      # Architecture design instructions
│   ├── project_developer_skill.md
│   └── ...                     # One .md file per role
│
├── agents/                     # Standalone R&D agents (used by CLI `run` command)
│   ├── base.py
│   ├── analyze_agent.py
│   ├── decompose_agent.py
│   ├── search_agent.py
│   ├── synthesize_agent.py
│   ├── report_agent.py
│   └── ...
│
├── actions/                    # ReAct loop primitives
│   ├── action.py               # LLMCallable type + Action base
│   ├── action_graph.py         # Directed action graph
│   ├── action_node.py          # Single action node
│   └── react_loop.py           # ReAct (Reason + Act) execution loop
│
├── flows/                      # (see above)
│
├── execution/
│   ├── task_runner.py          # Runs a single task with retry logic
│   └── registry.py             # Maps task types to executors
│
├── plan/
│   ├── planer.py               # Planner logic — generates structured plan
│   ├── model.py                # Plan data model
│   ├── plan_parser.py          # Parses LLM plan output into structured tasks
│   ├── plan_validator.py       # Validates plan completeness
│   ├── task.py                 # Task model
│   ├── clarify.py              # Clarification Q&A with user
│   ├── ask_review.py           # Sends plan to user for review
│   └── write_plan.py           # Writes final plan document
│
├── providers/
│   └── providers.py            # Provider factory (Anthropic/OpenAI/Gemini/Ollama/LMStudio)
│
├── schemas/
│   ├── agent_result.py         # AgentResult schema
│   ├── analysis.py             # Analysis output schema
│   ├── report.py               # Report schema
│   ├── synthesis.py            # Synthesis output schema
│   └── tool_inputs.py          # Tool input schemas
│
├── tools/
│   ├── registry.py             # Tool registry — builds default tool set
│   └── web_search.py           # Web search tool (injected into all roles)
│
├── infrastructure/
│   ├── logging.py              # Structured logging setup (structlog)
│   └── token_tracker.py        # Tracks token usage per role, formats report
│
└── utils/
    └── response_parser.py      # Parses LLM responses (JSON extraction, cleanup)
```

---

## Roles

| Role | Discord Name | Responsibility |
|------|-------------|----------------|
| `ProductManager` | Product Manager 🎯 | Orchestrates all phases, assigns tasks, reviews outputs |
| `BusinessAnalyst` | Business Analyst 📊 | User stories, acceptance criteria, business rules |
| `UIUXDesigner` | UI/UX Designer 🎨 | Wireframes, design system, UX notes |
| `ProjectDeveloper` | Project Developer 🚀 | Coordinates dev team, compiles report to PM |
| `SoftwareArchitect` | Software Architect 🏗️ | System design, DB schema, tech stack |
| `BackendDev` | Backend Dev 🖥️ | API, database, auth implementation |
| `FrontendDev` | Frontend Dev 💻 | UI implementation, component structure |
| `SecuritySpecialist` | Security Specialist 🔒 | Threat modeling, RLS/auth review |
| `DevOpsEngineer` | DevOps Engineer ⚙️ | CI/CD pipeline, infrastructure |
| `Tester` | Tester 🧪 | Test plans, test cases, E2E scenarios |
| `Reporter` | Reporter 📝 | Final report writing |
| `Planner` | Planner 🗂️ | Breaks requirement into structured task list |

---

## Setup

### 1. Install dependencies

```bash
uv sync
# or
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in:

```bash
# LLM Provider (anthropic | openai | gemini | ollama | lmstudio)
MA_LLM_PROVIDER=gemini
MA_GEMINI_API_KEY=your_key_here

# Discord Bot
MA_DISCORD_BOT_TOKEN=your_discord_token
MA_DISCORD_GUILD_ID=your_guild_id
MA_DISCORD_MAIN_CHANNEL_ID=your_channel_id

# Telegram Bot (optional)
TELEGRAM_BOT_TOKEN=your_telegram_token
```

### 3. Run

**Discord bot (production):**
```bash
uv run python main.py discord --provider gemini
```

**Telegram bot:**
```bash
uv run python main.py telegram --provider gemini
```

**CLI pipeline (R&D mode):**
```bash
uv run python main.py run "your research question" --provider anthropic
```

**Development (hot-reload):**
```bash
uv run python dev.py discord --provider gemini
```
> Warning: `dev.py` restarts the bot on every file save — any in-progress task will be interrupted. Use `main.py` for production or long-running tasks.

---

## Supported LLM Providers

| Provider | Env Var | Default Model |
|----------|---------|---------------|
| `anthropic` | `MA_ANTHROPIC_API_KEY` | `claude-opus-4-6` |
| `openai` | `MA_OPENAI_API_KEY` | `gpt-4o` |
| `gemini` | `MA_GEMINI_API_KEY` | `gemini-2.0-flash` |
| `ollama` | _(none)_ | `llama3.2` |
| `lmstudio` | _(none)_ | `local-model` |

Override model at runtime: `--model gemini-3.1-flash-lite-preview`

---

## Discord Usage

1. Invite the bot to your server
2. Send a message in the configured main channel describing your requirement
3. Bot creates a dedicated task channel and runs the full product flow
4. Each agent posts under its own identity (webhook)
5. PM asks for your approval before proceeding past the planning phase
