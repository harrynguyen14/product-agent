# Product Multi-Agent System

Hệ thống multi-agent AI cho phát triển sản phẩm phần mềm. Mỗi role trong quy trình (PM, BA, Architect, Developer, ...) là một Telegram bot độc lập. Các bot giao tiếp với nhau trong group thông qua `@mention` — giống như một team thực sự làm việc cùng nhau.

---

## Mục lục

1. [Kiến trúc tổng quan](#1-kiến-trúc-tổng-quan)
2. [Cấu trúc thư mục](#2-cấu-trúc-thư-mục)
3. [Các Role và trách nhiệm](#3-các-role-và-trách-nhiệm)
4. [Luồng hoạt động chi tiết](#4-luồng-hoạt-động-chi-tiết)
5. [Human-in-the-Loop Gate](#5-human-in-the-loop-gate)
6. [Kiến trúc kỹ thuật](#6-kiến-trúc-kỹ-thuật)
7. [LLM Providers](#7-llm-providers)
8. [Cài đặt và chạy](#8-cài-đặt-và-chạy)
9. [Cấu hình .env](#9-cấu-hình-env)
10. [Skill System](#10-skill-system)

---

## 1. Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────┐
│                   Telegram Group                        │
│                                                         │
│  User ──────────────────────────────────────────────►  │
│                                                         │
│  @pm_bot ──► @planner_bot ──► @ba_bot ──► @uiux_bot   │
│      │                                                  │
│      └──────────────────────────────────► @reporter_bot │
│                                                         │
│  @pd_bot ──► @arch_bot ──► @sec_bot ──► @devops_bot   │
│         ──► @fe_bot ──► @be_bot ──► @qa_bot            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Nguyên tắc thiết kế:**

- **1 role = 1 Telegram bot** — mỗi bot có token riêng, username riêng, chạy trong cùng 1 process
- **Orchestration qua @mention** — PM bot mention `@ba_bot [instruction]`, BA bot lắng nghe và phản hồi
- **Human-in-the-loop** — trước mỗi lần gọi một role, user phải xác nhận hoặc điều chỉnh
- **Stateless per chat** — mỗi Telegram group là 1 session độc lập
- **Tất cả bot chạy song song** — 1 lệnh `python main.py telegram` khởi động toàn bộ

---

## 2. Cấu trúc thư mục

```
product-multi-agent/
│
├── main.py                    # Entry point CLI — lệnh: telegram, providers
├── dev.py                     # Hot-reload runner cho development
├── .env                       # Tokens, API keys, cấu hình
│
├── config/
│   ├── settings.py            # AppConfig — toàn bộ cấu hình hệ thống
│   └── provider_config.py     # ProviderConfig — cấu hình từng LLM provider
│
├── core/
│   └── llm_factory.py         # LLMFactory — khởi tạo LLM callable từ config
│
├── telegram_bot/
│   ├── bot.py                 # Logic chính: PM/PD orchestration, worker handler
│   ├── session.py             # ChatSession — trạng thái mỗi group chat
│   ├── review_gate.py         # HumanGate — asyncio gate chờ user xác nhận
│   └── formatters.py          # Format tin nhắn, split 4096 chars, role headers
│
├── roles/
│   ├── base_role.py           # BaseRole — lớp cơ sở cho mọi role
│   ├── registry.py            # RoleRegistry — khởi tạo và cache role instances
│   ├── product_manager.py     # PM — orchestrator chính
│   ├── project_developer.py   # PD — orchestrator kỹ thuật
│   ├── planner.py             # Planner — lập kế hoạch dự án
│   ├── business_analyst.py    # BA — phân tích nghiệp vụ
│   ├── ui_ux_designer.py      # UIUX — thiết kế giao diện
│   ├── software_architect.py  # Arch — kiến trúc hệ thống
│   ├── security_specialist.py # Sec — bảo mật
│   ├── devops_engineer.py     # DevOps — CI/CD, hạ tầng
│   ├── frontend_dev.py        # FE — phát triển frontend
│   ├── backend_dev.py         # BE — phát triển backend
│   ├── tester.py              # QA — kiểm thử
│   ├── reporter.py            # Reporter — tổng hợp báo cáo
│   └── vietnamese_translator.py # Translator — dịch sang tiếng Việt
│
├── skills/
│   ├── loader.py              # Tải skill từ file .md
│   ├── skill_selector.py      # LLM chọn skill phù hợp động
│   ├── roles/                 # Skill files cho từng role
│   └── shared/                # Skill dùng chung (review, security, testing...)
│
├── providers/
│   └── providers.py           # Khởi tạo LangChain model theo provider
│
├── infrastructure/
│   └── logging.py             # Structured logging với structlog
│
├── tools/
│   ├── registry.py            # Tool registry (web search, ...)
│   └── web_search.py          # Web search via SerpAPI
│
└── utils/
    ├── llm_utils.py           # extract_content từ LLM response
    └── response_parser.py     # Parse structured output
```

---

## 3. Các Role và trách nhiệm

### Orchestrators

| Role | Slug | Quản lý |
|------|------|---------|
| **Product Manager** | `pm` | Planner → BA → UIUX → PD → Reporter |
| **Project Developer** | `pd` | Arch → Sec → DevOps → FE → BE → QA |

### PM sequence (thứ tự gọi)

```
Planner ──► BusinessAnalyst ──► UIUXDesigner ──► ProjectDeveloper ──► Reporter
```

### PD sequence (thứ tự gọi, nested trong PD)

```
SoftwareArchitect ──► SecuritySpecialist ──► DevOpsEngineer ──► FrontendDev ──► BackendDev ──► Tester
```

### Workers

| Role | Slug | Nhiệm vụ |
|------|------|----------|
| **Planner** | `planner` | Lập kế hoạch chi tiết, breakdown tasks |
| **Business Analyst** | `ba` | User stories, acceptance criteria, functional spec |
| **UI/UX Designer** | `uiux` | Wireframes, design system, UX guidelines |
| **Software Architect** | `arch` | System architecture, tech stack, module design |
| **Security Specialist** | `sec` | Threat modeling (STRIDE), OWASP, security review |
| **DevOps Engineer** | `devops` | CI/CD, Docker/K8s, monitoring, deployment |
| **Frontend Developer** | `fe` | UI components, state management, API integration |
| **Backend Developer** | `be` | API endpoints, database schema, business logic |
| **Tester** | `qa` | Test plans, test cases, quality assurance |
| **Reporter** | `reporter` | Tổng hợp toàn bộ output thành báo cáo cuối |
| **Translator** | `translator` | Dịch nội dung sang tiếng Việt |

---

## 4. Luồng hoạt động chi tiết

### 4.1 Khởi động hệ thống

```bash
python main.py telegram
```

1. Đọc `.env`, tìm tất cả `MA_TOKEN_<ROLE>` có giá trị
2. Với mỗi role có token: khởi tạo `AppConfig` với `bot_role=<slug>`
3. Build `Application` (python-telegram-bot) cho từng role
4. Gọi `app.bot.get_me()` để lấy username thực của bot
5. Tất cả app chạy song song qua `asyncio.TaskGroup`

### 4.2 User gửi yêu cầu

```
User → group: "Xây dựng hệ thống quản lý nhân sự"
```

**PM bot** nhận tin nhắn (là bot duy nhất lắng nghe message từ user thường):

1. Tạo `asyncio.Task` chạy `_pm_pipeline()`
2. PM (LLM) phân tích yêu cầu, soạn instruction cho **Planner**

### 4.3 Vòng lặp PM orchestration

Với mỗi role trong `PM_MANAGES = ["planner", "ba", "uiux", "pd", "reporter"]`:

```
┌─────────────────────────────────────────────────────┐
│  1. PM (LLM) soạn instruction cho role tiếp theo    │
│                                                     │
│  2. HumanGate.arm() + gửi tin hỏi user:            │
│     "🧑‍💼 BA sắp thực hiện: [instruction]            │
│      Gõ ok để tiếp tục hoặc gõ góp ý"              │
│                                                     │
│  3. Chờ user reply (asyncio.Future, timeout 600s)   │
│     ├── "ok" → tiếp tục với instruction hiện tại    │
│     └── "feedback" → append vào instruction → lặp   │
│                                                     │
│  4. PM mention role bot vào group:                  │
│     "@ba_bot [instruction đã confirm]"              │
│                                                     │
│  5. PM chờ role bot reply (role_reply_gate)         │
│                                                     │
│  6. Lưu output, tiếp role tiếp theo                 │
└─────────────────────────────────────────────────────┘
```

### 4.4 Worker bot nhận mention

Khi `@ba_bot` nhận được message có chứa `@ba_bot`:

1. Kiểm tra `_is_mentioned(text, my_username)` bằng regex
2. Strip `@ba_bot` khỏi text → lấy instruction thuần
3. Gọi `_handle_worker_mention()`:
   - Gửi status "📊 Business Analyst đang xử lý..."
   - `registry.get("BusinessAnalyst").run_task(instruction)`
   - Xóa status, gửi output vào group
4. PM bot nhận output (từ bot khác) → resolve `role_reply_gate`

### 4.5 PD orchestration (nested)

Khi PM mention `@pd_bot`, PD bot tự điều phối team kỹ thuật theo cùng pattern:

```
PM → @pd_bot [instruction]
         │
         ▼ (PD orchestrates)
    @arch_bot → @sec_bot → @devops_bot → @fe_bot → @be_bot → @qa_bot
         │
         ▼
    PD tổng hợp kết quả → reply vào group
         │
         ▼
    PM nhận → tiếp tục với @reporter_bot
```

Mỗi bước trong PD sequence cũng có **HumanGate** — user xác nhận trước khi PD mention sub-role.

### 4.6 Sequence đầy đủ

```
User: "Xây dựng hệ thống quản lý nhân sự"
  │
  ▼
[Gate] "Planner sắp làm: [instruction]" → User: "ok"
  │
  ▼
PM → @planner_bot → Planner output
  │
  ▼
[Gate] "BA sắp làm: [instruction]" → User: "ok"
  │
  ▼
PM → @ba_bot → BA output (user stories, spec)
  │
  ▼
[Gate] "UIUX sắp làm: [instruction]" → User: "ok"
  │
  ▼
PM → @uiux_bot → UIUX output (wireframes, design)
  │
  ▼
[Gate] "PD sắp làm: [instruction]" → User: "ok"
  │
  ▼
PM → @pd_bot
  │
  ├─ [Gate] "Architect sắp làm..." → User: "ok" → @arch_bot → output
  ├─ [Gate] "Security sắp làm..."  → User: "ok" → @sec_bot  → output
  ├─ [Gate] "DevOps sắp làm..."    → User: "ok" → @devops_bot → output
  ├─ [Gate] "FE sắp làm..."        → User: "ok" → @fe_bot   → output
  ├─ [Gate] "BE sắp làm..."        → User: "ok" → @be_bot   → output
  ├─ [Gate] "QA sắp làm..."        → User: "ok" → @qa_bot   → output
  └─ PD tổng hợp → reply group
  │
  ▼
[Gate] "Reporter sắp làm: [instruction]" → User: "ok"
  │
  ▼
PM → @reporter_bot → Báo cáo cuối cùng
  │
  ▼
✅ Hoàn thành
```

---

## 5. Human-in-the-Loop Gate

### Cơ chế

`HumanGate` (`telegram_bot/review_gate.py`) dùng `asyncio.Future` để suspend pipeline:

```python
# PM/PD arm gate và gửi tin hỏi
gate.arm()                          # tạo Future mới
await _send(chat, gate_prompt)      # gửi câu hỏi cho user

# Pipeline block tại đây (tối đa 600 giây)
reply = await gate.wait(timeout=600.0)

# Message handler của bot nhận tin user → resolve Future
gate.resolve(user_text)             # trong handle_message()
```

### Từ ngữ chấp nhận

User gõ một trong các từ sau để xác nhận:

```
ok  yes  y  tiếp  tiep  đồng ý  dong y  accept  oke  ok!
```

### Phản hồi thay vì xác nhận

Nếu user gõ bất kỳ text nào không phải từ chấp nhận:

1. Feedback được append vào instruction: `[Góp ý từ user: {feedback}]`
2. Bot thông báo "Đã nhận góp ý, điều chỉnh và hỏi lại..."
3. Gate arm lại, gửi instruction mới cho user xem lại
4. Lặp cho đến khi user gõ ok

### Session state

```python
@dataclass
class ChatSession:
    chat_id: int
    config: AppConfig
    gate: HumanGate              # Gate chờ user confirm
    role_reply_gate: HumanGate   # Gate chờ role bot reply
    expect_reply_from: str       # Slug của bot đang chờ
    active_task: asyncio.Task    # Pipeline task đang chạy
```

---

## 6. Kiến trúc kỹ thuật

### BaseRole

Mọi role kế thừa từ `BaseRole` (Pydantic BaseModel):

```python
class BaseRole(BaseModel):
    role_name: str       # "BusinessAnalyst"
    mention: str         # "ba"
    description: str     # Mô tả nhiệm vụ
    skill_file: str      # "ba_skill.md"
    extra_skills: list   # Skill file bổ sung
    api_docs: list       # API doc tham chiếu
```

**Prompt building** (2 lớp):
1. **Static**: `skill_file` + `extra_skills` + `api_docs` — load tại build time
2. **Dynamic**: LLM chọn thêm skill từ `skills/shared/` dựa trên task hiện tại

**LLM call flow:**
```
run_task(instruction)
  → respond(instruction)
  → _respond_plain()
  → _build_dynamic_prompt()    # system prompt với skills
  → LLM([SystemMessage, ...HumanMessage])
  → lưu vào history
  → trả về string
```

### RoleRegistry

Cache và lazy-init role instances cho 1 bot session:

```python
registry = RoleRegistry(llm=llm, raw_llm=raw_llm)
role = registry.get("BusinessAnalyst")  # tạo lần đầu, cache về sau
```

Hỗ trợ **multi-model routing** — mỗi role dùng model tối ưu:

| Model group | Roles | Lý do |
|-------------|-------|-------|
| `claude` (Anthropic) | Arch, BE, FE, Security | Code quality, reasoning |
| `gemini25` (Gemini 2.5 Flash) | PM, BA, PD, Planner | Long context, orchestration |
| `gemini20` (Gemini 2.0 Flash) | UIUX, DevOps, Tester, Reporter | Fast, lightweight |

### LLMFactory

```python
LLMFactory.build(config)        # → LLMCallable (async fn nhận messages → str)
LLMFactory.build_raw(config)    # → LangChain ChatModel (dùng cho multi-model)
LLMFactory.build_multi(config)  # → MultiModelSet(claude, gemini25, gemini20)
```

### Message routing trong bot

```
handle_message(update)
    │
    ├─ PM bot
    │   ├─ gate đang chờ?              → gate.resolve(text)
    │   ├─ từ bot khác + reply_gate?   → role_reply_gate.resolve(text)
    │   └─ từ user thường              → bắt đầu _pm_pipeline()
    │
    ├─ PD bot
    │   ├─ bị @mention?                → _pd_pipeline()
    │   ├─ gate đang chờ?              → gate.resolve(text)
    │   └─ từ sub-bot + reply_gate?    → role_reply_gate.resolve(text)
    │
    └─ Worker bot
        └─ bị @mention?                → _handle_worker_mention()
```

---

## 7. LLM Providers

Hỗ trợ 5 provider, cấu hình qua `.env`:

| Provider | Env var | Model mặc định |
|----------|---------|----------------|
| `anthropic` | `MA_ANTHROPIC_API_KEY` | `claude-opus-4-6` |
| `openai` | `MA_OPENAI_API_KEY` | `gpt-4o` |
| `gemini` | `MA_GEMINI_API_KEY` | `gemini-2.0-flash` |
| `ollama` | _(không cần)_ | `llama3.2` |
| `lmstudio` | _(không cần)_ | `local-model` |

**Fallback provider**: Khi một API key không có, tự động dùng fallback:

```env
MA_FALLBACK_PROVIDER=gemini
MA_FALLBACK_API_KEY=AIza...
MA_FALLBACK_MODEL=gemini-2.0-flash
```

---

## 8. Cài đặt và chạy

### Yêu cầu

- Python 3.12+
- uv (khuyến nghị) hoặc pip

### Cài đặt

```bash
# Clone repo
git clone <repo-url>
cd product-multi-agent

# Cài dependencies với uv
uv sync

# hoặc pip
pip install -r requirements.txt

# Copy và điền .env
cp .env.example .env
```

### Tạo bot trên Telegram

1. Mở Telegram, tìm `@BotFather`
2. Gửi `/newbot` — đặt tên và username cho bot
3. Lưu token nhận được vào `.env` (`MA_TOKEN_PM=...`)
4. Điền username vào `.env` (`MA_USERNAME_PM=my_pm_bot`)
5. Lặp lại cho các role cần dùng
6. Add tất cả bot vào Telegram group của project
7. Cấp quyền bot đọc tin nhắn trong group (tắt Privacy Mode qua BotFather)

### Chạy

```bash
# Chạy tất cả bot có token
python main.py telegram

# Chọn provider
python main.py telegram --provider anthropic

# Chọn model cụ thể
python main.py telegram --provider gemini --model gemini-2.5-flash-preview-04-17

# Development với hot-reload khi thay đổi code
python dev.py telegram --provider gemini

# Xem danh sách providers
python main.py providers
```

---

## 9. Cấu hình .env

```env
# ── LLM Provider ──────────────────────────────────────
MA_LLM_PROVIDER=gemini          # anthropic | openai | gemini | ollama | lmstudio

MA_ANTHROPIC_API_KEY=sk-ant-...
MA_GEMINI_API_KEY=AIza...
MA_OPENAI_API_KEY=sk-...

# ── Multi-model routing (tuỳ chọn) ───────────────────
MA_MULTI_MODEL_ENABLED=false
MA_ANTHROPIC_MULTI_PROVIDER=claude-sonnet-4-6
MA_GEMINI_REASONING_PROVIDER=gemini-2.5-flash-preview-04-17
MA_GEMINI_FAST_PROVIDER=gemini-2.0-flash

# ── Fallback ──────────────────────────────────────────
MA_FALLBACK_PROVIDER=gemini
MA_FALLBACK_API_KEY=AIza...
MA_FALLBACK_MODEL=gemini-2.0-flash

# ── Telegram Bot Tokens (điền role nào cần dùng) ──────
MA_TOKEN_PM=7xxxxxxx:AAF...
MA_TOKEN_PLANNER=8xxxxxxx:AAF...
MA_TOKEN_BA=9xxxxxxx:AAF...
MA_TOKEN_UIUX=
MA_TOKEN_PD=
MA_TOKEN_ARCH=
MA_TOKEN_SEC=
MA_TOKEN_DEVOPS=
MA_TOKEN_FE=
MA_TOKEN_BE=
MA_TOKEN_QA=
MA_TOKEN_REPORTER=

# ── Telegram Bot Usernames (@handle, không cần @) ─────
MA_USERNAME_PM=my_pm_bot
MA_USERNAME_PLANNER=my_planner_bot
MA_USERNAME_BA=my_ba_bot
MA_USERNAME_UIUX=my_uiux_bot
MA_USERNAME_PD=my_pd_bot
MA_USERNAME_ARCH=my_arch_bot
MA_USERNAME_SEC=my_sec_bot
MA_USERNAME_DEVOPS=my_devops_bot
MA_USERNAME_FE=my_fe_bot
MA_USERNAME_BE=my_be_bot
MA_USERNAME_QA=my_qa_bot
MA_USERNAME_REPORTER=my_reporter_bot

# ── Execution ─────────────────────────────────────────
MA_MAX_RETRIES=3
MA_TEMPERATURE=0.0
MA_MAX_TOKENS=4096
```

**Lưu ý:** Chỉ cần điền token cho các role muốn dùng. Bot không có token sẽ tự động bị bỏ qua khi khởi động.

---

## 10. Skill System

Mỗi role có **skill file** (Markdown) định nghĩa cách làm việc, được inject vào system prompt.

### Cấu trúc skills

```
skills/
├── roles/            # Skill riêng của từng role
│   ├── pm_skill.md
│   ├── ba_skill.md
│   ├── architect_skill.md
│   └── ...
└── shared/           # Skill dùng chung, LLM tự chọn theo task
    ├── review/       # Code review, plan review
    ├── security/     # Security patterns
    ├── testing/      # Testing strategies
    ├── quality/      # Code quality
    └── workflow/     # Workflow patterns
```

### Dynamic skill selection

Trước mỗi LLM call, hệ thống tự động chọn thêm skill phù hợp từ `skills/shared/`:

```
Task: "Thiết kế database schema cho hệ thống quản lý nhân sự"
  │
  ▼
LLM chọn skills: ["postgres_best_practices", "data_migration"]
  │
  ▼
Append vào system prompt → LLM có thêm context chuyên sâu
```

Tắt dynamic selection cho 1 role cụ thể:

```python
class MyRole(BaseRole):
    enable_skill_selection: bool = False
```

---

## Commands tham khảo

### Trong Telegram group

| Lệnh | Mô tả |
|------|-------|
| `/start` | Giới thiệu bot và hướng dẫn |
| `/cancel` | Dừng pipeline đang chạy |
| `/status` | Kiểm tra trạng thái pipeline |

### CLI

| Lệnh | Mô tả |
|------|-------|
| `python main.py telegram` | Khởi động tất cả bot có token |
| `python main.py telegram --provider anthropic` | Chỉ định LLM provider |
| `python main.py providers` | Liệt kê providers được hỗ trợ |
| `python dev.py telegram` | Chạy với hot-reload |
