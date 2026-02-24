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
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
