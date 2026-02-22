# 1. CLI and Entrypoint

The `cowork` CLI is the main interface to the Makix Enterprise Agentic Architecture. It allows you to run conversational agents, manage background tasks, handle traces, and fine-tune agent behavior.

## Installation

```bash
cd cli
pip install -e .

# Optional extras
pip install "cowork[documents]"   # PDF, PPTX, XLSX, DOCX generation
pip install "cowork[local-rag]"   # local vector search / embeddings
pip install "cowork[tools]"       # Google APIs (Calendar, Drive, Gmail)
pip install "cowork[all]"         # everything above
```

## Core Conversation Commands

### `cowork` or `cowork chat`
Starts an interactive chat session.
* Options:
  * `--session-id, -s <id>`: Resume a specific session.
  * `--trace`: Persist full workflow trace for each turn.
  * `--no-banner`: Skip the welcome banner rendering.

### `cowork run "<prompt>"`
Runs a one-shot agent run non-interactively and exits.
* Options:
  * `--session-id, -s <id>`: Run inside an existing session.
  * `--model, -m <model>`: Override the text model.
  * `--no-stream`: Disable token streaming.
  * `--trace`: Persist full workflow trace for this run.

## Session and State Management

* `/new` or `cowork chat` + `/new`: Start a new session.
* `/sessions` or `cowork sessions`: List all saved sessions.
* `/load <id>`: Load a session by ID or slug.
* `/workspace`: Manage workspace sessions (list, search, open).
* `/clear`: Clear the terminal screen.
* `/exit` or `/quit` or `/q`: Exit the interactive shell.

## Job & Cron Commands

Cowork has a built-in Sentinel Job Dashboard capable of surviving crashes and running in the background.

* `cowork jobs`: Show the Sentinel job dashboard.
* `/jobs clean`: Wipe all job history.
* `/jobs resume <job_id>`: Resume a paused or failed job.
* `cowork cron list`: List scheduled cron jobs.
* `cowork cron view <job_id>`: Show details of a specific cron job.
* `cowork cron run-pending`: Manually run all pending cron jobs.

## Memory & Tracing

* `cowork memory`: Show Memoria status summary.
* `/memory search <query>`: Perform semantic search against knowledge graph.
* `/memory add <sub> <pred> <obj>`: Manually add long-term memory facts.
* `/memory clear`: Clear all long-term memory.
* `/vector`: Alias for `/memory`.
* `cowork trace`: Render a saved trace in a terminal-readable timeline.
* `/trace full`: View full readable trace payloads.
* `/trace raw`: View raw JSON trace events.

## Configuration & Profiles

* `cowork setup`: Run the interactive setup wizard.
* `cowork config`: Show current configuration. Use `/config set <key> <value>` to update.
* `cowork ai`: Manage AI profiles (`list`, `add`, `switch`, `remove`, `save`).
* `cowork mm`: Manage multimodal service endpoints/models.
* `cowork tokens`: Show token usage across models.

## Reset
* `/reset`: **DANGER**. Wipes all persisted Cowork state under `~/.cowork/*`.
