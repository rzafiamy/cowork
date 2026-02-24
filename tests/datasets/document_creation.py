from pathlib import Path

test_cases = [
    {
        "category": "Document Creation",
        "name": "Create PDF Report",
        "prompts": [
            "Create a PDF report named 'market_analysis.pdf' with the title 'Market Trend 2026'. "
            "Add a section with heading 'Executive Summary' and text 'The market is growing rapidly in the AI sector.' "
            "And a few bullets: 'Growth: 25%', 'Main player: Makix'."
        ],
        "verify": lambda response, context: "✅ PDF created!" in response and "market_analysis.pdf" in response
    },
    {
        "category": "Document Creation",
        "name": "Create Excel Spreadsheet",
        "prompts": [
            "Create an Excel file 'sales_2026.xlsx' with a sheet 'Q1' containing headers 'Product' and 'Sales'. "
            "Add two rows: ['MakiX Pro', 50000] and ['MakiX Lite', 20000]."
        ],
        "verify": lambda response, context: "✅ XLSX created!" in response and "sales_2026.xlsx" in response
    },
    {
        "category": "Document Creation",
        "name": "Create Word Document",
        "prompts": [
            "Create a Word document 'outline.docx' titled 'Project Proposal'. "
            "Add a heading 'Scope' and some text 'This project covers AI agent orchestration.'."
        ],
        "verify": lambda response, context: "✅ DOCX created!" in response and "outline.docx" in response
    },
    {
        "category": "Document Creation",
        "name": "Create PPTX Presentation",
        "prompts": [
            "Create a PowerPoint 'vision_2026.pptx' titled 'The Future of AI'. "
            "Add one slide with title 'Agentic Architecture' and bullet points 'Autonomous', 'Skill-based'."
        ],
        "verify": lambda response, context: "✅ PPTX created!" in response and "vision_2026.pptx" in response
    }
]
