---
name: coding-tools
description: Inspect, edit, and validate codebase changes safely.
triggers:
  - code
  - implement
  - bug
  - refactor
  - test
trust_tier: 3
tool_categories:
  - CODING_TOOLS
permissions:
  categories:
    - CODING_TOOLS
  tools:
    - codebase_bash
    - codebase_grep
    - codebase_list_files
    - codebase_read_file
    - codebase_search_text
    - codebase_write_file
    - github_search
---
# Coding Tools Skill

Purpose: Inspect, edit, and validate codebase changes safely.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
