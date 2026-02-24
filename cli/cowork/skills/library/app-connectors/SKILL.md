---
name: app-connectors
description: Create/update notes and lightweight app connector records.
triggers:
  - notes
  - kanban
  - connector
  - task
  - storage
trust_tier: 3
tool_categories:
  - APP_CONNECTORS
permissions:
  categories:
    - APP_CONNECTORS
  tools:
    - kanban_add_task
    - notes_create
    - storage_write
---
# App Connectors Skill

Purpose: Create/update notes and lightweight app connector records.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
