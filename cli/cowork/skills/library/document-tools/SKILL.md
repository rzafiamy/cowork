---
name: document-tools
description: Powerful document writer skill for PDF, DOCX, XLSX, and PPTX creation.
triggers:
  - document
  - report
  - spreadsheet
  - excel
  - word
  - pdf
  - document-tools
  - create document
  - docx
  - xlsx
trust_tier: 3
tool_categories:
  - DOCUMENT_TOOLS
  - SEARCH_TOOLS
  - DATA_AND_UTILITY
  - SESSION_SCRATCHPAD
permissions:
  categories:
    - DOCUMENT_TOOLS
    - SEARCH_TOOLS
    - DATA_AND_UTILITY
    - SESSION_SCRATCHPAD
  tools:
    - document_create_docx
    - document_create_pdf
    - document_create_pptx
    - document_create_xlsx
    - google_cse_search
    - brave_search
    - firecrawl_scrape
    - image_generate
    - plotchar
    - gen_diagram
    - scratchpad_save
    - scratchpad_read_chunk
    - scratchpad_list
    - scratchpad_fork
    - scratchpad_edit_lines
    - scratchpad_append
    - scratchpad_get_outline
---
# Document Tools Skill

Purpose: Enable the end-to-end creation of professional documents, spreadsheets, and reports.

Workflow:

1. **Phase 1: Research & Structure**
   - Gather necessary data using `web_search` and `scrape_urls`.
   - Define the document structure (sections, columns) in the scratchpad.
   - For complex reports, create an outline first and save it to `ref:document_outline`.

2. **Phase 2: Data Extraction & Synthesis**
   - Extract key facts, metrics, and insights.
   - Format data for the target document type (e.g., JSON-like for sections or rows).
   - Use `gen_chart` or `gen_diagram` for visual data representation.

3. **Phase 3: Visual & Data Strategy (Media Planning)**
   - Identify sections that need visual support (charts for data, images for context).
   - **Data Visualization**: Use `gen_chart` (Charts.js) or `gen_diagram` (Mermaid) for structured data or flows.
   - **Image Generation**: Use `image_generate` to create high-quality, relevant visual assets.
   - For PDF and DOCX, images can be embedded directly via their absolute paths.

4. **Phase 4: Document Generation**
   - **Reports/Letters (PDF/DOCX)**: Use `document_create_pdf` or `document_create_docx`. Include headings, body text, and bullets.
   - **Data/Analysis (XLSX)**: Use `document_create_xlsx`. Organize by sheets with clear headers.
   - **Presentations (PPTX)**: Use `document_create_pptx` for narrative flow and visual impact.

5. **Phase 5: Finalization**
   - Report the workspace-relative path of the generated file (e.g., `artifacts/Annual_Report.pdf`).
   - Provide a direct open link: `/open artifacts/filename.ext`.

Guardrails:
- **Relative Paths**: Always use workspace-relative paths in output.
- **Valid JSON**: Ensure all JSON payloads for document creation are correctly formatted.
- **Precision**: For XLSX, ensure headers and rows are perfectly aligned.
- **No Fabrications**: If research data is missing, report it honestly; do not invent "placeholder" facts.
