---
name: cron-tools
description: Schedule, list, and remove background jobs.
triggers:
  - schedule
  - cron
  - reminder
  - job
  - recurring
trust_tier: 3
tool_categories:
  - CRON_TOOLS
permissions:
  categories:
    - CRON_TOOLS
  tools:
    - cron_delete
    - cron_list
    - cron_schedule
---
# Cron Tools Skill

Purpose: Schedule, list, and remove background jobs.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
