---
name: document-tools
description: Create structured documents (PDF/PPTX/XLSX/DOCX).
triggers:
  - pdf
  - pptx
  - docx
  - xlsx
  - document
trust_tier: 3
tool_categories:
  - DOCUMENT_TOOLS
permissions:
  categories:
    - DOCUMENT_TOOLS
  tools:
    - document_create_docx
    - document_create_pdf
    - document_create_pptx
    - document_create_xlsx
---
# Document Tools Skill

Purpose: Create structured documents (PDF/PPTX/XLSX/DOCX).

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. For PPTX requests, apply this method before tool execution:
   - Outcome: define audience, objective, and 1-line takeaway.
   - Story spine: open with context, build with evidence, close with action.
   - Slide economy: one key idea per slide, max 3-6 bullets, no paragraph walls.
   - Visual rhythm: alternate text-focused and visual-focused slides, reserve section dividers.
   - Data clarity: charts and numbers must support a clear claim.
4. Prefer `design_preset` (`executive`, `bold`, `minimal`) and use `key_message` per slide when possible.
5. If a tool returns an error, repair arguments or switch to a safer fallback.
6. After creation, always report the exact workspace-relative output path (for example `artifacts/file.pptx`).
7. Include a direct open method in the response (for example `/open artifacts/file.pptx`).
8. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
