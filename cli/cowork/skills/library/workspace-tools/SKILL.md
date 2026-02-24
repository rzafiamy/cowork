---
name: workspace-tools
description: Read/write/search workspace files and project notes.
triggers:
  - workspace
  - file
  - write
  - read
  - search
trust_tier: 3
tool_categories:
  - WORKSPACE_TOOLS
permissions:
  categories:
    - WORKSPACE_TOOLS
  tools:
    - workspace_context_update
    - workspace_list
    - workspace_note
    - workspace_read
    - workspace_search
    - workspace_write
---
# Workspace Tools Skill

Purpose: Read/write/search workspace files and project notes.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
