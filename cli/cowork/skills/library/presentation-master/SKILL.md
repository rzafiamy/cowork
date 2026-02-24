---
name: presentation-master
description: Orchestrate high-impact presentations from research and outlines to final PPTX creation with visual assets and charts.
triggers:
  - presentation
  - slides
  - pptx
  - pitch
  - deck
  - presentation-master
trust_tier: 3
tool_categories:
  - SEARCH_TOOLS
  - DOCUMENT_TOOLS
  - MULTIMODAL_TOOLS
  - DATA_AND_UTILITY
  - SESSION_SCRATCHPAD
permissions:
  categories:
    - SEARCH_TOOLS
    - DOCUMENT_TOOLS
    - MULTIMODAL_TOOLS
    - DATA_AND_UTILITY
    - SESSION_SCRATCHPAD
  tools:
    - web_search
    - scrape_urls
    - document_create_pptx
    - image_generate
    - gen_chart
    - gen_diagram
    - scratchpad_save
    - scratchpad_read_chunk
    - scratchpad_list
    - scratchpad_fork
    - scratchpad_edit_lines
    - scratchpad_append
    - scratchpad_get_outline
---
# Presentation Master Skill

Purpose: Orchestrate the end-to-end creation of professional, high-impact presentations.

Workflow:

1. **Phase 1: Foundation (The Goal & Outline)**
   - Start by defining the goal/audience in the scratchpad using key=`task_goal`.
   - Use `web_search` and `scrape_urls` to gather facts and evidence.
   - Create a detailed outline for the presentation, including slide-by-slide titles and core messages.
   - Save the outline to `ref:presentation_outline`.

2. **Phase 2: Narrative Development (Content Writing)**
   - For each slide, develop the full text (bullets, speaker notes, key takeaway).
   - Follow the "Slide Economy" rule: one key idea per slide, max 3-6 bullets.
   - Use `scratchpad_save` or `scratchpad_append` to build the full slide content draft (e.g., `ref:presentation_draft`).

3. **Phase 3: Visual & Data Strategy (Media Planning)**
   - Identify slides that need visual support.
   - **Image Generation**: First present all image prompts to the user in the chat, then use `image_generate` (Parallel execution preferred).
   - **Data Visualization**: Use `gen_chart` (Charts.js) or `gen_diagram` (Mermaid) for structured data or flows.
   - Save all visual references (paths or Mermaid code) into the draft.

4. **Phase 4: Assembly (PPTX Creation)**
   - Use `document_create_pptx` to assemble the final file.
   - Use a `design_preset` (`executive`, `bold`, `minimal`) aligned with the goal.
   - Map your developed content and visual assets to the corresponding slides.

5. **Phase 5: Finalization**
   - Report the exact workspace-relative path of the generated PPTX (e.g., `artifacts/Strategy_2026.pptx`).
   - Provide a direct open link: `/open artifacts/filename.pptx`.

Guardrails:
- **Always use `task_goal`**: Never start a presentation without anchoring the state in the scratchpad.
- **Narrative First**: Never call `image_generate` before the slide's core message is finalized.
- **Relative Paths Only**: When reporting the results, never use absolute OS paths.
- **Validate Assets**: Ensure chart JSON and Mermaid syntax are valid before calling tools.
- **No Fabrications**: If search fails or data is missing, report it honestly; do not invent "placeholder" facts.
