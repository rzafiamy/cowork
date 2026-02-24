---
name: multimodal-tools
description: Run vision, image generation, ASR, and TTS operations.
triggers:
  - image
  - vision
  - ocr
  - speech
  - audio
trust_tier: 3
tool_categories:
  - MULTIMODAL_TOOLS
permissions:
  categories:
    - MULTIMODAL_TOOLS
  tools:
    - image_generate
    - speech_to_text
    - text_to_speech
    - vision_analyze
---
# Multimodal Tools Skill

Purpose: Run vision, image generation, ASR, and TTS operations.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
