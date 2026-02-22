# 5. Tools and Execution

The Cowork Agent has a highly modular tool interface defined in `cli/cowork/tools/`. The **Meta-Router** narrows down which tools are available at any given time, but the **Execution Gateway** is responsible for safely running those tools.

## Tool Categories
Tools are split into domain-specific categories such as:
* **Utility**: `calc`, `get_time`, `gen_diagram`
* **Scratchpad/Workspace**: Session memory and file I/O operations.
* **Coding**: Codebase grep, reading/writing files, parsing github repos.
* **Cron**: Scheduling background agent tasks.
* **Connectors**: Database/external app connections (e.g. Kanban, external notes, email).
* **Document**: Creating PDFs, PPTX, Docx, etc.
* **Multimodal**: Vision, Image Generation, Transcribing audio, Text-to-Speech.

## MCP / External Tools
Cowork supports dynamically registering tools beyond the builtin ones. `ExternalToolAdapter` safely wraps external schemas into the `BaseTool` interface, allowing the agent to seamlessly interact with third-party APIs.

## The Firewall
The Execution Gateway passes every proposed tool execution through the **Cowork Firewall** (`config.py:FirewallManager`).
* By default, high-risk tools like `run_command` or destructive file edits prompt an interactive `ASK` flow. The CLI halts and asks the user `[Y/n]` before allowing the tool to execute.
* Configuration for the Firewall is stored in `~/.cowork/firewall.yaml`. Users can explicitly whitelist (`ALLOW`) or blacklist (`BLOCK`) specific tool schemas.
