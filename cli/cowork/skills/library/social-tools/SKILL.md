---
name: social-tools
description: Use social channels and messaging integrations.
triggers:
  - linkedin
  - whatsapp
  - social
  - profile
  - message
trust_tier: 4
tool_categories:
  - SOCIAL_TOOLS
permissions:
  categories:
    - SOCIAL_TOOLS
  tools:
    - linkedin_search
    - whatsapp_send_message
---
# Social Tools Skill

Purpose: Use social channels and messaging integrations.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
