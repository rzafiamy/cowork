---
name: document-tools
description: Powerful document writer skill for PDF, DOCX, XLSX, PPTX creation, including complex structures like illustrated books, kids stories, financial reports, official letters, and resumes.
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
  - book
  - story
  - kids story
  - presentation
  - slides
  - resume
  - letter
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
    - think
    - scratchpad_save
    - scratchpad_read_chunk
    - scratchpad_list
    - scratchpad_fork
    - scratchpad_edit_lines
    - scratchpad_append
    - scratchpad_get_outline
---
# Document Tools Skill

Purpose: Enable the end-to-end creation of professional documents, spreadsheets, reports, books, kids stories, official letters, resumes, and dynamic visual presentations.

Workflow:

1. **Phase 1: Research & Structure**
   - Gather necessary data using `web_search` and `scrape_urls`.
   - Define the document structure (sections, columns, chapters, pages) in the scratchpad.
   - For complex reports or multi-page books, create an outline first and save it to `ref:document_outline`.

2. **Phase 2: Data Extraction & Synthesis**
   - Extract key facts, metrics, and insights.
   - For creative works (stories, books), draft the narrative arc carefully.
   - Format data for the target document type (e.g., JSON-like for sections or rows).

3. **Phase 3: Visual & Data Strategy (Media Planning)**
   - Identify sections that need visual support (charts for data, images for context/illustrations).
   - **Data Visualization & Financials**: Use `plotchar` for generated visual charts (bar, pie, line) or `gen_diagram` for structured logical flows.
   - **Illustrations (Books/Stories)**: Use `image_generate` to create high-quality, relevant visual assets (e.g., vibrant kids storybook illustrations, character portraits).
   - For PDF and DOCX, images and plots can be embedded directly via their absolute paths returned by the generation tools.

4. **Phase 4: Document Generation (Formatting Strategies)**
   - **Reports/Official Letters (PDF/DOCX)**: Use `document_create_pdf` or `document_create_docx`. Structure official letters with formal headers, date, recipient, and sign-offs. Use clear headings and structured paragraphs.
   - **Resumes (PDF/DOCX)**: Organize heavily with bullet points, bold sections for Work History/Education, and concise formatting.
   - **Illustrated Books & Kids Stories (PDF/DOCX)**: Interleave text sections with generated images. Write engaging narrative text, generate an illustration for each major plot point using `image_generate`, and embed the absolute image paths adjacent to the text in the `sections` parameter.
   - **Financial Docs/Data Analysis (XLSX)**: Use `document_create_xlsx`. Organize by sheets with clear headers. Note: You should pair XLSX creation with `plotchar` outputs saved as images if visual dashboards are requested. 
   - **Presentations/Slides (PPTX)**: Use `document_create_pptx` for narrative flow, bulleted slides, and high visual impact. Use the `theme_color` and `design_preset` options.

5. **Phase 5: Finalization**
   - Report the workspace-relative path of the generated file (e.g., `artifacts/Annual_Report.pdf`, `artifacts/Space_Dog_Story.pdf`).
   - Provide a direct open link: `/open artifacts/filename.ext`.

Guardrails:
- **Relative Paths**: Always use workspace-relative paths in textual output. For embedding generated images using `sections`, use the exact paths given to you by the image/plot tools.
- **Valid JSON**: Ensure all JSON payloads for document creation are correctly formatted.
- **Precision**: For XLSX, ensure headers and rows are perfectly aligned.
- **Creative Integrity**: For stories/books, maintain consistent styling prompts for illustrations.
- **No Fabrications**: If research data is missing, report it honestly; do not invent "placeholder" facts.
