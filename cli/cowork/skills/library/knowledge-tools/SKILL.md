---
name: knowledge-tools
description: Use encyclopedic knowledge retrieval tools.
triggers:
  - wikipedia
  - encyclopedia
  - knowledge
  - article
  - topic
trust_tier: 2
tool_categories:
  - KNOWLEDGE_TOOLS
permissions:
  categories:
    - KNOWLEDGE_TOOLS
  tools:
    - wikipedia_article
    - wikipedia_search
---
# Knowledge Tools Skill

Purpose: Use encyclopedic knowledge retrieval tools.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
