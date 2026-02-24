---
name: search-tools
description: Perform web and engine search queries.
triggers:
  - search
  - lookup
  - find
  - web
  - query
trust_tier: 2
tool_categories:
  - SEARCH_TOOLS
permissions:
  categories:
    - SEARCH_TOOLS
  tools:
    - brave_search
    - google_cse_search
    - google_search
---
# Search Tools Skill

Purpose: Perform web and engine search queries.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
