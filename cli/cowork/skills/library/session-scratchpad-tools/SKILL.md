---
name: session-scratchpad-tools
description: Store and retrieve structured working memory in session scratchpad.
triggers:
  - scratchpad
  - save
  - memory
  - reference
  - context
trust_tier: 3
tool_categories:
  - SESSION_SCRATCHPAD
permissions:
  categories:
    - SESSION_SCRATCHPAD
  tools:
    - record_issue_solution
    - scratchpad_append
    - scratchpad_edit_lines
    - scratchpad_fork
    - scratchpad_get_outline
    - scratchpad_list
    - scratchpad_read_chunk
    - scratchpad_save
    - scratchpad_search
    - scratchpad_update_goal
---
# Session Scratchpad Tools Skill

Purpose: Store and retrieve structured working memory in session scratchpad.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
