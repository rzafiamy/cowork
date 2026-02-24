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
1. **Prompt Batching**: When generating images, aim to formulate and display all image prompts to the user in the chat FIRST.
2. **Tool Execution**: Only after presenting the planned prompts, call the `image_generate` tool for each prompt (prefer parallel execution).
3. **TTS Preparation**: When preparing text for the `text_to_speech` tool, ensure the content is optimized for professional spoken delivery:
    - **No Sections/Headings**: Use a singular, continuous narrative. Avoid titles, headings, dividers, or numbered lists that interrupt the flow.
    - **No Abbreviations**: Expand every technical term or abbreviation (e.g., "AI" to "Artificial Intelligence", "approx." to "approximately", "etc." to "and so on").
    - **Clean Text**: Remove all complex symbols, emojis, and technical markdown (tables, code snippets, or bracketed citations).
    - **Narrative Development**: The text should be developed with transitions that make it sound natural and authoritative when read aloud.
4. Prefer the smallest tool call that can complete the next step.
5. Validate required arguments before execution.
6. If a tool returns an error, repair arguments or switch to a safer fallback.
7. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
