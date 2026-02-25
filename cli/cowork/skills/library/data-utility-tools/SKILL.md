---
name: data-utility-tools
description: Run calculations, time/date checks, and chart utilities.
triggers:
  - calculate
  - math
  - time
  - diagram
  - chart
  - plot
  - plotchar
  - graph
  - graphique
trust_tier: 2
tool_categories:
  - DATA_AND_UTILITY
permissions:
  categories:
    - DATA_AND_UTILITY
  tools:
    - calc
    - gen_diagram
    - get_time
    - plotchar
---
# Data Utility Tools Skill

Purpose: Run calculations, time/date checks, and chart utilities.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
