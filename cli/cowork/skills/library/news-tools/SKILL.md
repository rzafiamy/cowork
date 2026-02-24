---
name: news-tools
description: Retrieve current headlines and news summaries.
triggers:
  - news
  - headline
  - latest
  - today
  - press
trust_tier: 2
tool_categories:
  - NEWS_TOOLS
permissions:
  categories:
    - NEWS_TOOLS
  tools:
    - newsapi_headlines
---
# News Tools Skill

Purpose: Retrieve current headlines and news summaries.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
