---
name: youtube-tools
description: Search, inspect, transcribe, and download YouTube media.
triggers:
  - youtube
  - transcript
  - video
  - metadata
  - download
trust_tier: 2
tool_categories:
  - YOUTUBE_TOOLS
permissions:
  categories:
    - YOUTUBE_TOOLS
  tools:
    - youtube_download
    - youtube_metadata
    - youtube_search
    - youtube_transcript
---
# Youtube Tools Skill

Purpose: Search, inspect, transcribe, and download YouTube media.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
