# 🧠 Intelligence & Reasoning

This document details the cognitive strategies used to maximize accuracy while minimizing latency and token costs.

---

## 🧭 Meta-Tool Routing (The Brain)
To prevent "Tool Fatigue" and context noise, we implement a **Dynamic Schema** strategy powered by a dedicated Router agent.

### 🚦 The Logic Flow (Current)
1.  **🔍 Router Classification**: Run a **T=0.0** routing call with JSON output.
2.  **🧯 Fallback Routing**: If the routing call fails or JSON parsing fails, use keyword fallback.
3.  **🎯 Just-In-Time Tool Schema**:
    *   `CONVERSATIONAL_ONLY` ⮕ no tool schema.
    *   Tool-capable routes ⮕ filtered tool schema.
4.  **🧩 Prompt Mode Selection**:
    *   Chat prompt for conversational-only.
    *   Workflow prompt for multi-step/tool turns.

### 📂 Classification Domains
- 🌍 **`SEARCH_AND_INFO`**: Primary knowledge retrieval and real-time data.
- 🎬 **`MEDIA_AND_ENTERTAINMENT`**: Image generation, Movies (TMDB), and YouTube.
- 👁️ **`VISION`**: Visual analysis, OCR, and object detection.
- 📊 **`DATA_AND_UTILITY`**: Math, Charting, Diagrams, and Time.
- 🧠 **`SESSION_SCRATCHPAD`**: Temporary "Work-RAM" for processing large data within a session. Volatile.
- 🔌 **`APP_CONNECTORS`**: Persistent productivity ecosystem integrations (Notes, Kanban, Calendar, Storage, etc.) for long-term workspace records.
- 💻 **`CODING_TOOLS`**: Unified code tools for GitHub/code research and project-root operations (list/read/search/grep/write).
- 💭 **`CONVERSATIONAL_ONLY`**: Minimal orchestration path for direct answers with no tools schema.

### 🛠️ Available Tools by Category

| Category | Tools | Description |
| :--- | :--- | :--- |
| **SEARCH_AND_INFO** | `web_search`, `wiki_get`, `scrape_urls`, `get_weather`, `get_bible_data`, `search_docs` | Web search, Wikipedia, scraping, weather, Bible data, and local document RAG. |
| **MEDIA_AND_ENTERTAINMENT** | `gen_image`, `yt_search`, `yt_meta`, `yt_transcript`, `tmdb_trending`, `tmdb_search` | DALL-E 3 image generation, full YouTube suite, and Movie DB integration. |
| **VISION** | `vision_analyze` | Multi-modal analysis of uploaded/stored images. |
| **DATA_AND_UTILITY** | `gen_chart`, `gen_diagram`, `calc`, `get_time` | Chart.js visualizer, Mermaid.js diagrams, math engine, and clock. |
| **SESSION_SCRATCHPAD** | `scratchpad_save`, `scratchpad_get_info`, `scratchpad_read_chunk`, `scratchpad_list`, `scratchpad_search` | Internal task-only storage. Data is purged when the session ends. |
| **APP_CONNECTORS** | `notes_create`, `kanban_add_task`, `cal_add_event`, `storage_write`, etc. | External database/app persistence. Use for explicit "Save to my records" commands. |

```mermaid
graph TD
    A["👤 User Prompt"] --> B{"🧭 Meta-Router"}
    B -- "Hello" --> C
    B -- "Research AI" --> D["🌍 Load SEARCH Tools"]
    B -- "Analyze Image" --> E["👁️ Load VISION Tools"]
    B -- "Low Confidence" --> G["🔥 Load ALL Tools"]
    C --> F("🤖 Chat Prompt Execution")
    D --> F
    E --> F
    G --> F
    F --> H["✅ Final Response"]
```

---

## 🌡️ Task-Aware Temperature Architecture
Precision is balanced with creativity through a tiered temperature strategy:

| 🌡️ Tier | Applying To | 🎯 Objective |
| :--- | :--- | :--- |
| **0.0** | Meta-Routing, JSON Schema | **Max Precision**: Deterministic & Structured. |
| **0.1** | **Planner (Phase 2.5)**, Context Compression | **Factual Integrity**: Deterministic plan structures and factual summaries. |
| **0.4** | Main Agent REACT Loop | **Balanced Logic**: Goal-oriented reasoning. |
| **0.7** | Chat & Session Titling | **Human Voice**: Engaging & creative tone. |

---

## 🗺️ Plan-then-Execute (Phase 2.5)
Inspired by **Erdogan et al. 2025** (“Plan-and-Act”, ICML 2025) and **GoalAct** (2025), the system now runs a
dedicated **Planner model** call **before** the REACT loop starts.

### How It Fits the Temperature Strategy
- **Planner** (T=0.1): Generates a deterministic, structured JSON plan — `goal`, `complexity`, ordered `steps`.
- **Executor** (T=0.4): Follows the injected `[EXECUTION PLAN]` inside the REACT loop.

### Separation of Concerns (Plan-and-Act Paradigm)
| Role | Temperature | Responsibility |
| :--- | :--- | :--- |
| **Planner** | 0.1 | Decomposes goal → ordered steps. Outputs JSON. |
| **Executor (REACT)** | 0.4 | Translates plan steps → tool calls + reasoning. |
| **Compressor** | 0.1 | Summarizes history when context is full. |
| **Router** | 0.0 | Classifies intent → tool categories. |

### Bypass Conditions
The planner is **skipped** (no latency hit) when:
- Turn is `CONVERSATIONAL_ONLY`
- `action_mode` is active (intent already known)
- Config has `plan_then_execute: false`
- Planner determines `complexity: simple` with a `direct_answer` step

### Config Key
```yaml
plan_then_execute: true    # default; set false to revert to pure REACT
model_planner: ""          # defaults to model_router if not set
```

## ⚡ Active Action Mode (Fast-Track)
When a user clicks a **Workflow Pill** or triggers a command:
1.  **⏩ Router Bypass**: Intent is already known; we skip classification to save ~1.5s.
2.  **🔒 Strict Tooling**: The Agent is locked to the specific toolset defined for that Action.
3.  **💉 Instruction Injection**: Custom workflow instructions are fused directly into the system prompt.

---

## 🔁 Step-Intersection Reasoning (Tool -> Reflection -> Next Inference)
Inside the REACT loop, the critical reasoning transition is:
1. LLM emits tool calls.
2. Tools execute and return outputs.
3. Agent generates a compact structured reflection from tool outcomes.
4. Reflection is appended to messages.
5. LLM performs next-step reasoning from both raw results and structured state.

Current reflection schema:
- `tool`
- `status` (`ok` / `partial` / `error` / `blocked`)
- `finding`
- `next_action`

Operational persistence:
- A rolling `run_step_ledger` is saved to scratchpad during the run.
- This acts as short-term execution memory and supports continuity if context gets dense.

---

## 🚨 Status Banner Policy
- Goal-status banners (`✅/⚠️/❌`) are reserved for **step-limit self-assessment** turns only.
- Normal turns should answer directly without banner framing.

---

## 📅 Search Freshness & Temporal Context
To combat "stale data" hallucinations:
*   **🕰️ Date Anchoring**: The current system date is injected into every prompt.
*   **🗜️ Temporal Clamps**: `google_search` includes a `date_restrict` parameter based on user-defined freshness (24h, 1wk, 1mo).
*   **📑 Scrape-First**: Agents are biased to perform 1 search and then deep-dive via `scrape_web` rather than repetitive shallow searching.
