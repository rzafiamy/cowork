---
name: media-tools
description: Handle media conversion and entertainment metadata lookups.
triggers:
  - media
  - movie
  - tmdb
  - convert
  - video
trust_tier: 3
tool_categories:
  - MEDIA_TOOLS
permissions:
  categories:
    - MEDIA_TOOLS
  tools:
    - media_convert
    - tmdb_details
    - tmdb_search
---
# Media Tools Skill

Purpose: Handle media conversion and entertainment metadata lookups.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
