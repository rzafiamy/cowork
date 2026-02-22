# Cowork CLI Reference

This is the dedicated command-line reference for `cowork`, grouped by category.

## 1. Command Structure

`cowork` has:

- Root command (no global options)
- Subcommands (each defines its own options)
- Nested command groups: `mm`, `cron`, and `sessions`

Because options are subcommand-scoped, use:

- `cowork chat --trace` (valid)
- `cowork --trace` (invalid)

## 2. Core Conversation Commands

### `cowork`

Starts interactive chat (same behavior as `cowork chat`).

### `cowork chat`

Start an interactive session.

Options:

- `--session-id, -s <id>`: resume a specific session
- `--no-banner`: skip banner rendering
- `--trace / --no-trace`: enable/disable detailed workflow trace logs for this run

Examples:

```bash
cowork chat
cowork chat --session-id 2b9db9a5
cowork chat --trace
cowork chat --no-trace --no-banner
```

### `cowork run "<prompt>"`

Run one prompt non-interactively and exit.

Arguments:

- `prompt`: required task/prompt text

Options:

- `--session-id, -s <id>`: run inside an existing session
- `--model, -m <model>`: override `model_text` for this run
- `--no-stream`: disable token streaming
- `--trace / --no-trace`: enable/disable detailed workflow trace logs for this run

Examples:

```bash
cowork run "Summarize this repo"
cowork run "Generate changelog draft" --model gpt-4o-mini
cowork run "Plan migration tasks" --trace
```

Runtime behavior notes:

- Turns are always meta-routed first, then tool schemas are selected from routed categories.
- Goal status banners (`✅/⚠️/❌`) are reserved for step-limit self-assessment responses, not normal turns.
- Memory persistence is selective: durable profile/preference/project-state turns are prioritized over generic one-off Q&A.

## 3. Session and State Commands

### `cowork sessions` (or `cowork session`)

Manage saved conversation sessions.

Actions:

- `list` (default): list saved sessions
- `rm <index>`: permanently delete a session by its list index
- `retitle`: batch re-title all sessions using AI analysis (exactly 12 words, dash-separated)
- `search <pattern>`: regex-based search across titles, content, summaries, and triplets

Options for `search`:

- `--title <regex>`: match only titles
- `--content <regex>`: match only message content
- `--summary <regex>`: match only session summaries
- `--triplets <regex>`: match only knowledge triplets

Examples:

```bash
cowork sessions
cowork session rm 5
cowork sessions retitle
cowork session search --title "quantum"
cowork session search "[0-9]{4}-logic"
```

### `cowork jobs [action]`

Manage Sentinel job history.

Arguments:

- `action` (optional): currently supports `clean`

Examples:

```bash
cowork jobs
cowork jobs clean
```

### `cowork memory`

Show Memoria status summary.

## 4. Configuration and Connectivity

### `cowork setup`

Run interactive setup wizard.

### `cowork config`

Show current configuration.

Options:

- `--set KEY VALUE`: set one or more config values

Examples:

```bash
cowork config
cowork config --set show_trace true
cowork config --set max_steps 20 --set stream false
```

### `cowork ping`

Test API endpoint connectivity and model listing.

### `cowork tokens`

Show cumulative token usage.

Options:

- `--reset`: reset token counters

Examples:

```bash
cowork tokens
cowork tokens --reset
```

## 5. Tool and Profile Management

### `cowork tools`

List currently available tools (built-in + configured external).

### `cowork ai <action> [args...]`

Manage named AI profiles.

Actions:

- `list`
- `add`
- `switch`
- `remove`
- `save`

Examples:

```bash
cowork ai list
cowork ai add my-openai https://api.openai.com/v1 gpt-4o-mini "default profile"
cowork ai switch my-openai
cowork ai remove my-openai
cowork ai save baseline
```

## 6. Multi-Modal Service Commands

### `cowork mm status`

Show configured endpoints/models/tokens for multimodal services.

### `cowork mm set <service> <field> <value>`

Set multimodal service configuration.

Arguments:

- `service`: `vision | images | asr | tts`
- `field`: `endpoint | token | model`
- `value`: value to store

Examples:

```bash
cowork mm status
cowork mm set vision endpoint https://api.openai.com/v1
cowork mm set vision token sk-...
cowork mm set images model dall-e-3
```

## 7. Cron Commands

### `cowork cron list`

List scheduled cron jobs.

### `cowork cron view <job_id>`

Show details and last result of one cron job.

### `cowork cron rm <job_id>`

Remove a cron job.

### `cowork cron run-pending`

Run all pending cron jobs now.

Options:

- `--interactive`: allow firewall confirmation prompts

Examples:

```bash
cowork cron list
cowork cron view daily_report
cowork cron rm daily_report
cowork cron run-pending --interactive
```

## 8. Trace Viewer Command

### `cowork trace`

Render a saved trace in terminal-readable form.

Options:

- `--file <path>`: open a specific JSONL trace file
- `--session-id, -s <id>`: pick latest trace from a session
- `--raw`: print raw JSON events
- `--full / --summary`: full payloads or keys-only summary (default: full)

Examples:

```bash
cowork trace
cowork trace --summary
cowork trace --raw
cowork trace --file ~/.cowork/traces/<session_id>/<trace>.jsonl
```

## 9. Interactive Slash Commands (Inside `cowork chat`)

These are chat-time commands, not shell subcommands:

- `/help`
- `/new`
- `/sessions`, `/session`
- `/sessions rm <index>`
- `/sessions retitle`
- `/sessions search <regex>`
- `/load <session_id_or_number>`
- `/jobs`, `/jobs clean`, `/jobs resume <job_id>`
- `/config`, `/config set <key> <value>`
- `/scratchpad`
- `/workspace`, `/workspace list`, `/workspace search <q>`, `/workspace open`, `/workspace clean`
- `/trace`
- `/trace full`
- `/trace raw`
- `/trace path`
- `/tokens`, `/tokens reset`
- `/cron`, `/cron list`, `/cron view <id>`, `/cron rm <id>`
- `/memory`, `/memory list`, `/memory search <q>`, `/memory add <sub> <pred> <obj>`, `/memory summarize`, `/memory rm <id>`, `/memory clear`, `/memory compress`
- `/vector` (alias for `/memory`)
- `/tools`
- `/ai`, `/ai add ...`, `/ai switch <name>`, `/ai remove <name>`, `/ai save [name]`
- `/model <name>`
- `/mm` and `/mm <service> <endpoint|token|model> <value>`
- `/clear`
- `/exit`

## 10. Trace Logging Quick Reference

- One run: `cowork run "..." --trace`
- Interactive session: `cowork chat --trace`
- Set default: `cowork config --set show_trace true`
- Disable per run: `--no-trace`

Trace files are written to:

- `~/.cowork/workspace/<session-slug>/traces/*.jsonl` (workspace-backed sessions)
- `~/.cowork/traces/<session_id>/*.jsonl` (fallback)

## 11. CLI Lifecycle & Boot Sequence

Every time the `cowork` CLI is invoked, it follows a standard initialization sequence to ensure environment integrity and clean state:

1.  **Firewall Verification**: Validates the integrity of `firewall.yaml` to ensure security policies are loadable.
2.  **Ghost Session Cleanup**: Automatically scans the `~/.cowork/sessions/` directory and permanently deletes any "empty" sessions (files with zero messages). This prevents clutter from abandoned CLI starts.
3.  **Config Validation**: Checks if `~/.cowork/config.json` exists and contains required keys. If not, it triggers the interactive `setup` wizard.
4.  **Session Initialization**: 
    *   If `--session-id` is provided, it attempts to load that specific session.
    *   Otherwise, it starts as a fresh session.
5.  **Background Services**: Starts the background cron scheduler to monitor and execute pending agentic jobs.
6.  **UI Welcome**: Renders the dashboard showing current model, endpoint connectivity, and session status (in interactive mode).
