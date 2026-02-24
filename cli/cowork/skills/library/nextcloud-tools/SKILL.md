---
name: nextcloud-tools
description: Operate on Nextcloud files and folders.
triggers:
  - nextcloud
  - upload
  - download
  - folder
  - search
trust_tier: 4
tool_categories:
  - NEXTCLOUD_TOOLS
permissions:
  categories:
    - NEXTCLOUD_TOOLS
  tools:
    - nextcloud_create_folder
    - nextcloud_delete
    - nextcloud_download
    - nextcloud_list
    - nextcloud_search
    - nextcloud_upload
---
# Nextcloud Tools Skill

Purpose: Operate on Nextcloud files and folders.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
