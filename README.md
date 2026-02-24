# 🤖 Cowork — Makix Enterprise Agentic CLI

> **A powerful autonomous AI coworker built on the Makix Enterprise Agentic Architecture.**

```
  ██████╗ ██████╗ ██╗    ██╗ ██████╗ ██████╗ ██╗  ██╗
 ██╔════╝██╔═══██╗██║    ██║██╔═══██╗██╔══██╗██║ ██╔╝
 ██║     ██║   ██║██║ █╗ ██║██║   ██║██████╔╝█████╔╝
 ██║     ██║   ██║██║███╗██║██║   ██║██╔══██╗██╔═██╗
 ╚██████╗╚██████╔╝╚███╔███╔╝╚██████╔╝██║  ██║██║  ██╗
  ╚═════╝ ╚═════╝  ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
```

---

## 🏗️ Architecture

Each user message is processed end-to-end through a 5-phase pipeline:

| Phase | Component | Description |
|-------|-----------|-------------|
| 🛡️ Phase 1 | **Input Gatekeeper** | Token estimation; large inputs automatically offloaded to scratchpad |
| 🧠 Phase 2 | **Meta-Router + Skill Runtime** | Intent classification at T=0.0, then progressive skill activation/trust gating + tool schema calibration |
| 🤖 Phase 3 | **REACT Loop** | Iterative Reason → Act → Observe with parallel tool execution |
| 🗜️ Phase 4 | **Context Compressor** | Map-Reduce history summarisation at T=0.1 when token budget is tight |
| 🚀 Phase 5 | **Memory Ingestion** | Selective Memoria update for durable profile/preferences/project-state facts |

### Step Budget & Completion Guarantee

The REACT loop runs for up to `max_steps` (default: 15) iterations. At the limit:

1. **Self-assessment call** — the agent makes one final tool-free LLM call to honestly report what was achieved and what remains
2. **Structured status** — response uses `✅ GOAL ACHIEVED`, `⚠️ GOAL PARTIALLY ACHIEVED`, or `❌ GOAL NOT ACHIEVED` only for step-limit self-assessment turns
3. **Continuation handoff** — the agent tells the user exactly what to say to continue in the next turn
4. **No hallucination** — the agent is explicitly forbidden from fabricating completed work

---

## 🧩 Skills Runtime (Progressive Disclosure)

Cowork injects `SKILL.md` guidance in three levels to keep prompts lean:

1. **Always-on TOC**: a lightweight `[SKILL LIBRARY METADATA]` list is injected every turn.
2. **Activation**: one best-matching skill can be activated from user intent + routed categories.
3. **Scoped loading**: full instructions and explicit resources are loaded only for the active skill, then filtered through trust tiers.

Skill safety controls:

- Trust gates can block suspicious or mismatched skills before instruction injection.
- Tool access is filtered by trust tier and manifest permissions.
- If a skill over-restricts tools to an empty set, runtime falls back to the routed toolset to avoid dead-ends.

---

## 📚 Documentation

The architecture and behavior of Cowork are documented in detail:
1. [CLI and Entrypoint](docs/new_docs/01_CLI_and_Entrypoint.md)
2. [Agent and Reasoning](docs/new_docs/02_Agent_and_Reasoning.md)
3. [Meta-Routing](docs/new_docs/03_Meta_Routing.md)
4. [Context and Memory](docs/new_docs/04_Context_and_Memory.md)
5. [Tools and Execution](docs/new_docs/05_Tools_and_Execution.md)
6. [Configuration and Profiles](docs/new_docs/06_Configuration_and_Profiles.md)
7. [Background Jobs and Tracing](docs/new_docs/07_Background_Jobs_and_Tracing.md)

---

## 🚀 Quick Start

Full command catalog: `docs/CLI_REFERENCE.md`

### Install

```bash
cd cli
pip install -e .

# Optional extras
pip install "cowork[documents]"   # PDF, PPTX, XLSX, DOCX generation
pip install "cowork[local-rag]"   # local vector search / embeddings
pip install "cowork[tools]"       # Google APIs (Calendar, Drive, Gmail)
pip install "cowork[all]"         # everything above
```

### Configure

```bash
cowork setup
# or set env vars directly:
export OPENAI_API_KEY=sk-...
export COWORK_API_ENDPOINT=https://api.openai.com/v1
```

### Run

```bash
cowork              # Interactive chat (default)
cowork chat         # Same as above
cowork run "Research the latest AI news"   # One-shot non-interactive
cowork chat --trace                        # Persist full workflow trace for each turn
cowork run "..." --trace                   # Persist full workflow trace for this run
cowork trace                               # Read latest trace in readable timeline
cowork ping         # Test API connectivity
cowork sessions     # List all sessions
cowork jobs         # Sentinel job dashboard
cowork memory       # Memoria status
cowork config       # Show configuration
```

---

## 💬 Interactive Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/new` | Start a new session |
| `/sessions` | List all sessions |
| `/load <id>` | Load a session by ID or slug |
| `/memory` | Show Memoria status |
| `/memory clear` | Clear all long-term memory |
| `/jobs` | Sentinel job dashboard |
| `/config` | Show current configuration |
| `/config set <key> <value>` | Update a config value |
| `/scratchpad` | List scratchpad entries |
| `/trace` | Show last job trace (step-by-step) |
| `/trace full` | Show full readable trace payloads |
| `/trace raw` | Show raw JSON trace events |
| `/trace path` | Show current trace file path |
| `/workspace` | Show workspace session files |
| `/clear` | Clear the terminal |
| `/exit` | Exit |

---

## ⚡ Action Pills (Hashtags)

Prefix your message with a hashtag to **fast-track routing** and bypass the Meta-Router:

| Pill | Category | Example |
|------|----------|---------|
| `#research` | SEARCH_AND_INFO | `#research latest AI benchmarks` |
| `#task` | APP_CONNECTORS | `#task add review PR to kanban` |
| `#calc` | DATA_AND_UTILITY | `#calc compound interest at 5% for 10 years` |
| `#coding` | CODING_TOOLS + WORKSPACE_TOOLS | `#coding build my freelancer AI landing page` |
| `#note` | APP_CONNECTORS | `#note meeting summary: decided on Python` |

Routing now always runs through the Meta-Router first, then tool schema is selected from routed categories.

---

## 🛠️ Available Tools

### 🧰 Built-in (always available)

| Category | Tool names |
|----------|-----------|
| 📝 SESSION_SCRATCHPAD | `scratchpad_save`, `scratchpad_list`, `scratchpad_read_chunk`, `scratchpad_search`, `scratchpad_update_goal` |
| 📊 DATA_AND_UTILITY | `calc`, `get_time`, `gen_diagram` |
| 💻 CODING_TOOLS | `github_search`, `codebase_list_files`, `codebase_read_file`, `codebase_search_text`, `codebase_grep`, `codebase_write_file` |
| 🔌 APP_CONNECTORS | `notes_create`, `kanban_add_task`, `storage_write`, `get_weather` |
| 📁 WORKSPACE_TOOLS | `workspace_write`, `workspace_read`, `workspace_list`, `workspace_note`, `workspace_context_update`, `workspace_search` |
| 📄 DOCUMENT_TOOLS | `document_create_pdf`, `document_create_pptx`, `document_create_xlsx`, `document_create_docx` |

### 🌐 External (requires API key / OAuth)

| Category | Tool names | Key env var |
|----------|-----------|-------------|
| 🌍 SEARCH_TOOLS | `web_search` | `BRAVE_API_KEY` |
| 📖 KNOWLEDGE_TOOLS | `wiki_get` | *(none)* |
| 🎬 YOUTUBE_TOOLS | `youtube_transcript`, `youtube_search` | *(none)* |
| 🔗 WEB_TOOLS | `scrape_url` | `FIRECRAWL_API_KEY` |
| ☁️ WEATHER_TOOLS | `get_weather` | `OPENWEATHERMAP_API_KEY` |
| 📰 NEWS_TOOLS | `news_search` | `NEWS_API_KEY` |
| 💻 CODING_TOOLS (external subset) | `github_search` | `GITHUB_TOKEN` |
| 💬 COMMUNICATION_TOOLS | `smtp_send_email` *(+ attachments, HTML)*, `telegram_send_message`, `slack_send_message`, `twitter_post_tweet` | `SMTP_*`, `TELEGRAM_BOT_TOKEN`, `SLACK_BOT_TOKEN`, `TWITTER_BEARER_TOKEN` |
| 📅 GOOGLE_TOOLS | `google_calendar_events`, `google_calendar_create_event`, `google_drive_search`, `google_drive_upload_text`, `gmail_send_email` *(+ attachments, HTML)* | `google_credentials.json` |
| 🎞️ MEDIA_TOOLS | `tmdb_search_movie` | `TMDB_API_KEY` |
| 👁️ VISION | `analyze_image` | *(uses model endpoint)* |

---

### Code Output Root

`codebase_*` tools write inside a dedicated Cowork area by default:

- Session-backed: `~/.cowork/workspace/<session-slug>/artifacts/codebase/`
- Fallback: `~/.cowork/workspace/_coding/artifacts/codebase/`

Override only if needed:

```bash
export COWORK_PROJECT_ROOT=/absolute/path
```

---

## 🎯 Task Anchoring (Multi-Step Memory)

For long, iterative tasks (slide decks, reports, comprehensive research, code), the agent maintains a **task anchor** in the scratchpad:

1. **On start** — calls `scratchpad_update_goal` with a structured goal block  
2. **On follow-up turns** — reads `task_goal` first before acting (instant context recovery)  
3. **After each refinement** — updates `task_goal` to reflect new state and remaining steps  
4. **The scratchpad index** is injected live into every system prompt so the agent sees it immediately

This means the agent recovers full context from a single tool call, even if the conversation is compressed or a new session is opened.

---

## 📁 File Structure

```
~/.cowork/
├── config.json              # Configuration (API endpoint, model, limits)
├── jobs.json                # Sentinel job queue (crash-proof background jobs)
├── sessions/                # Conversation history (OpenAI-format messages)
│   └── <session_id>.json
├── scratchpad/              # Per-session pass-by-reference blobs
│   └── <session_id>/
│       ├── task_goal.txt    # 🎯 Task anchor (multi-step context)
│       └── _index.json
├── memoria/                 # Long-term knowledge graph
│   ├── kg_<user_id>.json    # Subject-predicate-object triplets + EWA scores
│   └── summary_<sid>.json   # Rolling session summaries
├── workspace/               # Human-readable session workspace folders
│   └── <session-slug>/
│       ├── session.json     # Metadata + full message history
│       ├── context.md       # Living context doc (agent-writable)
│       ├── artifacts/       # Files produced by the agent (PDF, PPTX, code…)
│       ├── notes/           # Structured notes
│       └── scratchpad/      # Workspace-level blobs
├── google_credentials.json  # Google OAuth client credentials (optional)
└── google_token.json        # Google OAuth access token (auto-created)
```

---

## ⚙️ Configuration Reference

Config lives in `~/.cowork/config.json`. Change at runtime with `/config set <key> <value>`.

| Setting | Default | Description |
|---------|---------|-------------|
| `api_endpoint` | `https://api.openai.com/v1` | OpenAI-compatible base URL |
| `api_key` | — | LLM API key |
| `model_text` | `gpt-4o-mini` | Main reasoning + generation model |
| `model_router` | `gpt-4o-mini` | Meta-routing classifier (T=0.0) |
| `model_compress` | `gpt-4o-mini` | Context compression model (T=0.1) |
| `max_steps` | `15` | Max REACT loop iterations per turn |
| `max_total_tool_calls` | `30` | Hard cap on total tool calls per turn |
| `max_tool_calls_per_step` | `5` | Max parallel tool calls per step |
| `context_limit_tokens` | `6000` | Trigger threshold for history compression |
| `temperature_agent` | `0.4` | Agent reasoning temperature |
| `memory_min_similarity` | `0.2` | Minimum semantic similarity for memory retrieval |
| `memory_min_weight` | `0.015` | Minimum decayed relevance score for memory retrieval |
| `memory_topic_overlap_min` | `1` | Minimum keyword overlap between query and memory fact |
| `memory_high_similarity_bypass` | `0.55` | Allows highly similar facts through even with low term overlap |
| `stream` | `true` | Enable streaming output in the terminal |

Works with any OpenAI-compatible API: **OpenAI, Ollama, LM Studio, Together AI, Groq**, etc.

---

## 🧠 Memoria (Long-Term Memory)

Cowork maintains a **Knowledge Graph** of facts extracted from durable user context:

- Extracts `(subject, predicate, object)` triplets from durable user profile/preference/project-state messages
- Applies **Exponential Weighted Average (EWA)** temporal decay for relevance scoring
- Uses semantic + topical relevance gates during retrieval to avoid unrelated memories
- Uses a recency fallback when semantic retrieval returns nothing (keeps continuity on low-signal turns)
- Maintains rolling session summaries only when the user turn is durable enough to persist
- Prunes non-durable/transient facts from long-term memory with `cowork memory prune`
- All stored locally in `~/.cowork/memoria/` — no external vector DB required

---

## 📄 Document Generation

The `document_create_*` tools produce real, editable files saved to the workspace `artifacts/` folder. Pass the returned path directly to email-send tools for one-shot "create and send" workflows.

| Tool | Library | Capabilities |
|------|---------|-------------|
| `document_create_pdf` | reportlab | Headings, paragraphs, bullet lists, author, styled layout |
| `document_create_pptx` | python-pptx | Cover slide + content slides, bullet points, custom theme color |
| `document_create_xlsx` | openpyxl | Multiple sheets, styled headers, alternating rows, auto-width columns |
| `document_create_docx` | python-docx | Headings (H1–H3), paragraphs, bullet lists, embedded tables |

---

## 💌 Email with Attachments

Both `smtp_send_email` and `gmail_send_email` accept:
- `attachments`: list of absolute file paths (workspace artifacts work directly)
- `html`: boolean — set to `true` for HTML body

Example flow: `document_create_pdf` → returns path → pass to `smtp_send_email(attachments=[path])`.

---

*Built with ❤️ on the Makix Enterprise Agentic Architecture*
## 🧾 Workflow Trace Logging

Enable detailed trace logging when running `cowork`:

- `cowork chat --trace`
- `cowork run "..." --trace`
- Disable explicitly with `--no-trace`
- Set default with `/config set show_trace true`

Each run writes a JSONL trace containing full agent workflow events:

- If session has a workspace folder: `~/.cowork/workspace/<session-slug>/traces/*.jsonl`
- Otherwise: `~/.cowork/traces/<session_id>/*.jsonl`
