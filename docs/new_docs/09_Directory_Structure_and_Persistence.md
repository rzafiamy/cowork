# 9. Directory Structure and Persistence

Cowork adopts a highly file-system driven approach to persistence. All application state, from API configurations to chat history and generated artifacts, is localized to the `~/.cowork/` directory.

To ensure clarity and maintain an enterprise-grade separation of concerns, the directory is segmented into distinct concepts: **Memory**, **Workspaces**, and **Storage**. For a detailed view of how these folders relate to each other logically, see **[11. Concept & Data Relationships](./11_Concept_Relationships.md)**.

## The `~/.cowork/` Root Directory

```text
~/.cowork/
├── config.json            # Base system configuration (model, tokens)
├── firewall.yaml          # Tool execution security rules
├── ai_profiles.json       # Configured remote LLM endpoints/profiles
├── api_cache/             # Disk-Based TTL cache for HTTP requests
├── memoria/               # SQLite database for Long-Term Memory (RAG)
├── sessions/              # Raw conversational history arrays
├── scratchpad/            # Background text buffer & context pointers
├── workspace/             # Human-readable task deliverables & outputs
└── storage/               # Global shared resources and connector data
```

---

## Separation of Concerns: Session vs. Workspace vs. Storage

A common point of confusion is how and why Cowork separates Session data from Workspace data and Global Storage. They serve fundamentally different layers of the AI interaction lifecycle.

### 1. The Session Engine (`sessions/` & `scratchpad/`)
The Session is strictly the **short-term memory and conversational state**. 
* **`sessions/<session_id>.json`**: An array of human and assistant messages sent to the LLM endpoint during a chat.
* **`scratchpad/<session_id>/`**: If the agent reads a massive 2000-line codebase file, it does not inject 2000 lines into the prompt array (`sessions/`). Instead, it saves the file to the `scratchpad/` and returns a localized reference pointer (e.g., `ref:main-py`). This preserves the context window. 

*Data in these folders is temporal and technical. It represents "what the AI is currently thinking about."*

### 2. The Workspace Deliverables (`workspace/<slug>/`)
The Workspace is the **human-facing output folder** mapped specifically to a Session. 
When you start a new conversation (e.g., "Design the UI layout"), a corresponding workspace folder is generated (`~/.cowork/workspace/design-the-ui-layout/`). It holds the actual work produced:
* **`artifacts/`**: Final deliverables created by the agent, such as PDFs, PowerPoint presentations, or cleanly formatted python scripts.
* **`notes/`**: Structured markdown notes summarizing research or meetings.
* **`context.md`**: A living markdown document continuously updated by the agent to track milestones and the overall state of the task.

*Data in this folder is siloed per conversation. It represents "what the AI produced during this specific task."*

### 3. Global Storage (`storage/`)
The Storage bucket is the **cross-session persistent state**. 
Unlike a Workspace folder (which is tied to one chat session), the Storage directory holds universal data that needs to be accessed by any agent, at any time, in any future session.
* External connectors, global plugins, or centralized knowledge graphs use the `storage_write` tool to persist data here.
* If you tell the agent to "save my API key to the global configuration", it will write to `storage/` rather than the temporal `workspace/`.

*Data in this folder is global. It represents "application-wide state independent of a specific conversation."*

### 4. Long-Term Memory (`memoria/`)
Unlike the isolated conversational session data, Memoria is a **semantic SQLite vector database** spanning all interactions.
* When you converse with the agent, facts about you and the environment are extracted into Subject-Predicate-Object triplets and stored here.
* This is why the agent can remember your language preference across different sessions, even though the sessions themselves are siloed.
* *More details in [04_Context_and_Memory.md](./04_Context_and_Memory.md)*.

### 5. API Cache (`api_cache/`)
This is the **network optimization layer**. 
* When the agent uses an HTTP connector (e.g. searching the web, checking weather, or scraping a URL), the raw response is hashed and saved here.
* This ensures that if the agent re-runs a tool or script asking for the exact same URL, it returns instantly without costing API credits or rate limits.
* *More details in [08_Storage_and_Caching.md](./08_Storage_and_Caching.md)*.

### 6. Configuration & Security (`config.json`, `firewall.yaml`, `ai_profiles.json`)
These files constitute the **root application configuration**.
* **`config.json`**: Tracks the active base definitions, token usage paths, and active model string. Any tokens or API keys saved here are automatically masked or stripped in favor of `.env` overrides.
* **`ai_profiles.json`**: Lists different LLM endpoints that can be hot-swapped mid-session using `/profile switch`.
* **`firewall.yaml`**: The security policy defining which tools the agent is permitted to run autonomously versus ones that prompt an interactive `[Y/n]` (like executing shell commands).
