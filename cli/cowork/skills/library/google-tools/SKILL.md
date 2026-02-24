---
name: google-tools
description: Use Google calendar, drive, and gmail integrations.
triggers:
  - gmail
  - google
  - calendar
  - drive
  - event
trust_tier: 4
tool_categories:
  - GOOGLE_TOOLS
permissions:
  categories:
    - GOOGLE_TOOLS
  tools:
    - gmail_send_email
    - google_calendar_create_event
    - google_calendar_events
    - google_drive_search
    - google_drive_upload_text
---
# Google Tools Skill

Purpose: Use Google calendar, drive, and gmail integrations.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
