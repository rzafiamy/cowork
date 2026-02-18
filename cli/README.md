# 🤖 Cowork — Makix Enterprise Agentic CLI

> **A powerful autonomous AI coworker built on the Manager-Worker agentic architecture.**

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

Cowork implements the full **Makix Enterprise Agentic System** in a beautiful terminal interface:

| Phase | Component | Description |
|-------|-----------|-------------|
| 🛡️ Phase 1 | **Input Gatekeeper** | Token estimation, scratchpad offloading |
| 🧠 Phase 2 | **Meta-Router** | Intent classification at T=0.0, dynamic tool schema loading |
| 🤖 Phase 3 | **REACT Loop** | Recursive reasoning + parallel tool execution |
| 🖇️ Phase 4 | **Context Compressor** | Map-Reduce compression at T=0.1 |
| 🚀 Phase 5 | **Background Persistence** | Non-blocking Memoria update |

---

## 🚀 Quick Start

### Install
```bash
cd cli
pip install -e .
```

### Configure
```bash
cowork setup
# or set env vars:
export OPENAI_API_KEY=sk-...
export COWORK_API_ENDPOINT=https://api.openai.com/v1
```

### Run
```bash
cowork          # Interactive chat
cowork chat     # Same as above
cowork run "Research the latest AI news"   # One-shot
cowork ping     # Test connectivity
cowork sessions # List sessions
cowork jobs     # Job dashboard
cowork memory   # Memory status
cowork config   # Show config
```

---

## 💬 Interactive Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/new` | Start a new session |
| `/sessions` | List all sessions |
| `/load <id>` | Load a session |
| `/memory` | Show Memoria status |
| `/memory clear` | Clear all memory |
| `/jobs` | Sentinel job dashboard |
| `/config` | Show configuration |
| `/config set <key> <value>` | Update config |
| `/scratchpad` | List scratchpad contents |
| `/trace` | Show last job trace |
| `/clear` | Clear terminal |
| `/exit` | Exit |

---

## ⚡ Action Pills (Hashtags)

Type hashtags to fast-track routing (bypasses the Meta-Router):

| Pill | Category | Example |
|------|----------|---------|
| `#research` | SEARCH_AND_INFO | `#research latest AI papers` |
| `#task` | APP_CONNECTORS | `#task add review PR to kanban` |
| `#calc` | DATA_AND_UTILITY | `#calc compound interest formula` |
| `#note` | APP_CONNECTORS | `#note save this meeting summary` |

---

## 🛠️ Available Tools

| Category | Tools |
|----------|-------|
| 🌍 SEARCH_AND_INFO | `web_search`, `wiki_get`, `scrape_urls`, `get_weather` |
| 📊 DATA_AND_UTILITY | `calc`, `get_time`, `gen_diagram` |
| 📝 SESSION_SCRATCHPAD | `scratchpad_save`, `scratchpad_list`, `scratchpad_read_chunk`, `scratchpad_search` |
| 🔌 APP_CONNECTORS | `notes_create`, `kanban_add_task`, `storage_write` |

---

## ⚙️ Configuration

Config is stored in `~/.cowork/config.json`. Key settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `api_endpoint` | `https://api.openai.com/v1` | OpenAI-compatible endpoint |
| `api_key` | — | API key |
| `model_text` | `gpt-4o-mini` | Main reasoning model |
| `model_router` | `gpt-4o-mini` | Meta-routing model (T=0.0) |
| `model_compress` | `gpt-4o-mini` | Compression model (T=0.1) |
| `max_steps` | `15` | Max REACT loop iterations |
| `max_total_tool_calls` | `30` | Budget guard |
| `context_limit_tokens` | `6000` | History compression threshold |
| `stream` | `true` | Enable streaming output |

Works with any OpenAI-compatible API: **OpenAI, Ollama, LM Studio, Together AI, Groq**, etc.

---

## 🧠 Memoria (Long-Term Memory)

Cowork maintains a **Knowledge Graph** of facts about you across sessions:
- Extracts subject-predicate-object triplets from your messages
- Applies **Exponential Weighted Average (EWA)** temporal decay for relevance
- Maintains rolling session summaries
- Stored locally in `~/.cowork/memoria/`

---

## 📁 File Structure

```
~/.cowork/
├── config.json          # Configuration
├── jobs.json            # Sentinel job queue (crash-proof)
├── sessions/            # Conversation history
│   └── <session_id>.json
├── scratchpad/          # Pass-by-reference memory
│   └── <session_id>/
├── memoria/             # Long-term knowledge graph
│   ├── kg_<user_id>.json
│   └── summary_<session_id>.json
└── storage/             # Workspace file storage
```

---

*Built with ❤️ on the Makix Enterprise Agentic Architecture*
