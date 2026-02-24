---
name: communication-tools
description: Send outbound messages through communication channels.
triggers:
  - email
  - slack
  - telegram
  - tweet
  - message
trust_tier: 4
tool_categories:
  - COMMUNICATION_TOOLS
permissions:
  categories:
    - COMMUNICATION_TOOLS
  tools:
    - slack_send_message
    - smtp_send_email
    - telegram_send_message
    - twitter_post_tweet
---
# Communication Tools Skill

Purpose: Send outbound messages through communication channels.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.
5. Before any send action, verify destination fields (email/chat/channel/ID) are explicitly provided by the user.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
- Never invent recipients, channels, usernames, phone numbers, or URLs.
- If destination details are missing, ambiguous, or look like placeholders, ask the user to confirm before sending.
