"""
📄 Document Creation Tools
Tools for generating PDF, PPTX (PowerPoint), XLSX (Excel), and DOCX (Word)
files directly into the session workspace artifacts folder.

Libraries:
  • PDF  → reportlab    (vector PDF, no external deps)
  • PPTX → python-pptx  (native .pptx files)
  • XLSX → openpyxl     (native .xlsx files)
  • DOCX → python-docx  (native .docx files)
"""

import json
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import BaseTool
from ...workspace import workspace_manager, WORKSPACE_ROOT


# ─── Workspace helper ─────────────────────────────────────────────────────────

def _get_artifacts_dir(scratchpad) -> Path:
    """Return the workspace artifacts/ path, falling back to WORKSPACE_ROOT."""
    if scratchpad:
        for info in workspace_manager.list_all():
            if info["session_id"] == scratchpad.session_id:
                from ...workspace import WorkspaceSession
                ws = WorkspaceSession.load(info["slug"])
                if ws:
                    return ws.artifacts_path
    return WORKSPACE_ROOT


def _safe_filename(name: str) -> str:
    """Strip path traversal, keep only the base name."""
    return Path(name).name


# ─── PDF ─────────────────────────────────────────────────────────────────────

class DocumentCreatePdfTool(BaseTool):

    @property
    def name(self) -> str:
        return "document_create_pdf"

    @property
    def description(self) -> str:
        return (
            "Create a PDF document and save it to the workspace artifacts folder. "
            "Accepts a title and a list of sections as JSON: "
            "[{\"heading\": \"...\", \"text\": \"...\", \"bullets\": [\"...\"]}, ...]. "
            "Returns the absolute file path for use with email attachments."
        )

    @property
    def category(self) -> str:
        return "DOCUMENT_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Output filename, e.g. 'report.pdf'",
                },
                "title": {
                    "type": "string",
                    "description": "Document title shown at the top",
                },
                "sections": {
                    "type": "string",
                    "description": (
                        "JSON array of sections. Each section: "
                        "{\"heading\": str (optional), \"text\": str (optional), "
                        "\"bullets\": [str] (optional)}. "
                        "Example: [{\"heading\": \"Intro\", \"text\": \"Hello world.\", \"bullets\": [\"Point A\", \"Point B\"]}]"
                    ),
                },
                "author": {
                    "type": "string",
                    "description": "Author name shown in the document footer (optional)",
                },
            },
            "required": ["filename", "title", "sections"],
        }

    def execute(self, filename: str, title: str, sections: str, author: str = "") -> str:
        self._emit(f"📄 Creating PDF: '{filename}'...")
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer,
                ListFlowable, ListItem, HRFlowable,
            )
        except ImportError:
            return "❌ reportlab not installed. Run: pip install reportlab"

        try:
            section_data: List[dict] = json.loads(sections)
        except json.JSONDecodeError as e:
            return f"❌ Invalid JSON in 'sections': {e}"

        artifacts_dir = _get_artifacts_dir(self.scratchpad)
        out_path = artifacts_dir / _safe_filename(filename)
        if not out_path.suffix:
            out_path = out_path.with_suffix(".pdf")

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=25 * mm,
            bottomMargin=20 * mm,
            title=title,
            author=author,
        )

        styles = getSampleStyleSheet()
        # Custom styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Title"],
            fontSize=24,
            spaceAfter=8,
            textColor=colors.HexColor("#1a1a2e"),
        )
        h1_style = ParagraphStyle(
            "H1",
            parent=styles["Heading1"],
            fontSize=15,
            spaceBefore=14,
            spaceAfter=4,
            textColor=colors.HexColor("#16213e"),
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=10,
            leading=15,
            spaceAfter=6,
        )
        bullet_style = ParagraphStyle(
            "Bullet",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            leftIndent=12,
        )

        story = [
            Paragraph(title, title_style),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#16213e")),
            Spacer(1, 6 * mm),
        ]
        if author:
            story.append(Paragraph(f"<i>Author: {author}</i>", styles["Italic"]))
            story.append(Spacer(1, 4 * mm))

        for sec in section_data:
            heading = sec.get("heading", "")
            text = sec.get("text", "")
            bullets = sec.get("bullets", [])

            if heading:
                story.append(Paragraph(heading, h1_style))
            if text:
                # Escape XML special chars for ReportLab
                safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(safe_text, body_style))
            if bullets:
                items = [
                    ListItem(Paragraph(b.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), bullet_style))
                    for b in bullets
                ]
                story.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=18))
            story.append(Spacer(1, 3 * mm))

        doc.build(story)
        out_path.write_bytes(buf.getvalue())
        size_kb = out_path.stat().st_size // 1024

        return (
            f"✅ PDF created!\n"
            f"• File: `{out_path.name}`\n"
            f"• Path: `{out_path}`\n"
            f"• Size: {size_kb} KB\n"
            f"• Sections: {len(section_data)}"
        )


# ─── PPTX ────────────────────────────────────────────────────────────────────

class DocumentCreatePptxTool(BaseTool):

    @property
    def name(self) -> str:
        return "document_create_pptx"

    @property
    def description(self) -> str:
        return (
            "Create a PowerPoint (.pptx) presentation and save it to the workspace artifacts folder. "
            "Accepts a list of slides as JSON: "
            "[{\"title\": \"...\", \"content\": \"...\", \"bullets\": [\"...\"]}, ...]. "
            "The first slide is automatically a title slide. "
            "Returns the absolute file path for use with email attachments."
        )

    @property
    def category(self) -> str:
        return "DOCUMENT_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Output filename, e.g. 'presentation.pptx'",
                },
                "title": {
                    "type": "string",
                    "description": "Presentation overall title (used on the cover slide)",
                },
                "subtitle": {
                    "type": "string",
                    "description": "Subtitle or author shown on the cover slide (optional)",
                },
                "slides": {
                    "type": "string",
                    "description": (
                        "JSON array of slides. Each slide: "
                        "{\"title\": str, \"content\": str (optional), \"bullets\": [str] (optional)}. "
                        "Example: [{\"title\": \"Introduction\", \"bullets\": [\"Key point 1\", \"Key point 2\"]}]"
                    ),
                },
                "theme_color": {
                    "type": "string",
                    "description": "Hex color for the accent/header color, e.g. '#2563EB' (optional, default dark blue)",
                },
            },
            "required": ["filename", "title", "slides"],
        }

    def execute(
        self,
        filename: str,
        title: str,
        slides: str,
        subtitle: str = "",
        theme_color: str = "#1a1a2e",
    ) -> str:
        self._emit(f"📊 Creating PPTX: '{filename}'...")
        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt, Emu
            from pptx.dml.color import RGBColor
            from pptx.enum.text import PP_ALIGN
        except ImportError:
            return "❌ python-pptx not installed. Run: pip install python-pptx"

        try:
            slides_data: List[dict] = json.loads(slides)
        except json.JSONDecodeError as e:
            return f"❌ Invalid JSON in 'slides': {e}"

        artifacts_dir = _get_artifacts_dir(self.scratchpad)
        out_path = artifacts_dir / _safe_filename(filename)
        if not out_path.suffix:
            out_path = out_path.with_suffix(".pptx")

        # Parse hex color → RGBColor
        def _rgb(hex_color: str) -> RGBColor:
            h = hex_color.lstrip("#")
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            try:
                return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
            except Exception:
                return RGBColor(0x1A, 0x1A, 0x2E)

        accent = _rgb(theme_color)
        white = RGBColor(0xFF, 0xFF, 0xFF)
        dark_text = RGBColor(0x1A, 0x1A, 0x2E)

        prs = Presentation()
        prs.slide_width = Inches(13.33)
        prs.slide_height = Inches(7.5)

        blank_layout = prs.slide_layouts[6]  # blank

        def _add_rect(slide, left, top, width, height, fill_rgb):
            from pptx.util import Emu
            shape = slide.shapes.add_shape(
                1,  # MSO_SHAPE_TYPE.RECTANGLE
                Inches(left), Inches(top), Inches(width), Inches(height)
            )
            shape.fill.solid()
            shape.fill.fore_color.rgb = fill_rgb
            shape.line.fill.background()
            return shape

        def _add_textbox(slide, left, top, width, height, text, font_size, bold=False, color=None, align=PP_ALIGN.LEFT, word_wrap=True):
            txb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
            tf = txb.text_frame
            tf.word_wrap = word_wrap
            p = tf.paragraphs[0]
            p.alignment = align
            run = p.add_run()
            run.text = text
            run.font.size = Pt(font_size)
            run.font.bold = bold
            if color:
                run.font.color.rgb = color
            return txb

        # ── Cover slide ──────────────────────────────────────────────────────
        cover = prs.slides.add_slide(blank_layout)
        _add_rect(cover, 0, 0, 13.33, 7.5, accent)  # full-bleed background
        _add_rect(cover, 0, 5.5, 13.33, 2.0, RGBColor(0x0D, 0x0D, 0x1A))  # bottom strip
        _add_textbox(cover, 0.8, 2.0, 11.73, 2.0, title, 40, bold=True, color=white, align=PP_ALIGN.LEFT)
        if subtitle:
            _add_textbox(cover, 0.8, 4.2, 11.73, 0.8, subtitle, 20, color=RGBColor(0xCC, 0xCC, 0xFF), align=PP_ALIGN.LEFT)

        # ── Content slides ───────────────────────────────────────────────────
        for i, slide_data in enumerate(slides_data):
            sl = prs.slides.add_slide(blank_layout)
            slide_title = slide_data.get("title", f"Slide {i + 1}")
            content_text = slide_data.get("content", "")
            bullets = slide_data.get("bullets", [])

            # Header bar
            _add_rect(sl, 0, 0, 13.33, 1.3, accent)
            _add_textbox(sl, 0.3, 0.15, 12.5, 1.0, slide_title, 24, bold=True, color=white)

            # Slide number
            _add_textbox(sl, 12.3, 0.0, 1.0, 0.6, str(i + 2), 12, color=RGBColor(0xCC, 0xCC, 0xFF), align=PP_ALIGN.RIGHT)

            # Content area
            y_offset = 1.5
            if content_text:
                _add_textbox(sl, 0.5, y_offset, 12.33, 1.2, content_text, 16, color=dark_text)
                y_offset += 1.4

            if bullets:
                from pptx.util import Pt as _Pt
                bullet_box = sl.shapes.add_textbox(Inches(0.5), Inches(y_offset), Inches(12.33), Inches(7.5 - y_offset - 0.3))
                tf = bullet_box.text_frame
                tf.word_wrap = True
                for idx, bullet in enumerate(bullets):
                    p = tf.add_paragraph() if idx > 0 else tf.paragraphs[0]
                    p.text = f"  •  {bullet}"
                    p.space_before = _Pt(6)
                    for run in p.runs:
                        run.font.size = _Pt(18)
                        run.font.color.rgb = dark_text

        prs.save(str(out_path))
        size_kb = out_path.stat().st_size // 1024

        return (
            f"✅ PPTX created!\n"
            f"• File: `{out_path.name}`\n"
            f"• Path: `{out_path}`\n"
            f"• Size: {size_kb} KB\n"
            f"• Slides: {1 + len(slides_data)} (1 cover + {len(slides_data)} content)"
        )


# ─── XLSX ────────────────────────────────────────────────────────────────────

class DocumentCreateXlsxTool(BaseTool):

    @property
    def name(self) -> str:
        return "document_create_xlsx"

    @property
    def description(self) -> str:
        return (
            "Create an Excel (.xlsx) spreadsheet and save it to the workspace artifacts folder. "
            "Accepts sheet data as JSON: "
            "{\"Sheet Name\": {\"headers\": [\"col1\", \"col2\"], \"rows\": [[\"a\", 1], [\"b\", 2]]}, ...}. "
            "Supports multiple sheets, auto-column widths, and styled headers. "
            "Returns the absolute file path."
        )

    @property
    def category(self) -> str:
        return "DOCUMENT_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Output filename, e.g. 'data.xlsx'",
                },
                "sheets": {
                    "type": "string",
                    "description": (
                        "JSON object mapping sheet name → sheet data. "
                        "Sheet data: {\"headers\": [str, ...], \"rows\": [[value, ...], ...]}. "
                        "Example: {\"Sales\": {\"headers\": [\"Month\", \"Revenue\"], \"rows\": [[\"Jan\", 50000], [\"Feb\", 62000]]}}"
                    ),
                },
                "title": {
                    "type": "string",
                    "description": "Document title stored in file metadata (optional)",
                },
            },
            "required": ["filename", "sheets"],
        }

    def execute(self, filename: str, sheets: str, title: str = "") -> str:
        self._emit(f"📊 Creating XLSX: '{filename}'...")
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            return "❌ openpyxl not installed. Run: pip install openpyxl"

        try:
            sheets_data: dict = json.loads(sheets)
        except json.JSONDecodeError as e:
            return f"❌ Invalid JSON in 'sheets': {e}"

        artifacts_dir = _get_artifacts_dir(self.scratchpad)
        out_path = artifacts_dir / _safe_filename(filename)
        if not out_path.suffix:
            out_path = out_path.with_suffix(".xlsx")

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # Remove default sheet

        # Styles
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill("solid", fgColor="1A1A2E")
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style="thin", color="DDDDDD"),
            right=Side(style="thin", color="DDDDDD"),
            top=Side(style="thin", color="DDDDDD"),
            bottom=Side(style="thin", color="DDDDDD"),
        )
        alt_fill = PatternFill("solid", fgColor="F0F0F8")

        total_rows = 0
        for sheet_name, sheet_data in sheets_data.items():
            ws = wb.create_sheet(title=sheet_name[:31])  # Excel limit: 31 chars
            headers = sheet_data.get("headers", [])
            rows = sheet_data.get("rows", [])

            # Header row
            ws.row_dimensions[1].height = 30
            for col_idx, header in enumerate(headers, start=1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_align
                cell.border = thin_border

            # Data rows
            for row_idx, row in enumerate(rows, start=2):
                ws.row_dimensions[row_idx].height = 18
                fill = alt_fill if row_idx % 2 == 0 else None
                for col_idx, value in enumerate(row, start=1):
                    cell = ws.cell(row=row_idx, column=col_idx, value=value)
                    cell.alignment = left_align
                    cell.border = thin_border
                    if fill:
                        cell.fill = fill

            # Auto-fit column widths
            for col_idx, col_cells in enumerate(ws.columns, start=1):
                max_len = max(
                    (len(str(c.value)) if c.value is not None else 0 for c in col_cells),
                    default=8,
                )
                ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 50)

            # Freeze top row
            ws.freeze_panes = "A2"
            total_rows += len(rows)

        if title:
            wb.properties.title = title

        wb.save(str(out_path))
        size_kb = out_path.stat().st_size // 1024

        sheet_names = list(sheets_data.keys())
        return (
            f"✅ XLSX created!\n"
            f"• File: `{out_path.name}`\n"
            f"• Path: `{out_path}`\n"
            f"• Size: {size_kb} KB\n"
            f"• Sheets: {', '.join(sheet_names)}\n"
            f"• Total rows: {total_rows}"
        )


# ─── DOCX ────────────────────────────────────────────────────────────────────

class DocumentCreateDocxTool(BaseTool):

    @property
    def name(self) -> str:
        return "document_create_docx"

    @property
    def description(self) -> str:
        return (
            "Create a Word document (.docx) and save it to the workspace artifacts folder. "
            "Accepts a list of sections as JSON: "
            "[{\"heading\": \"...\", \"level\": 1, \"text\": \"...\", \"bullets\": [\"...\"], \"table\": {\"headers\": [...], \"rows\": [[...]]}}, ...]. "
            "Returns the absolute file path for use with email attachments."
        )

    @property
    def category(self) -> str:
        return "DOCUMENT_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Output filename, e.g. 'report.docx'",
                },
                "title": {
                    "type": "string",
                    "description": "Document title shown as the top heading",
                },
                "sections": {
                    "type": "string",
                    "description": (
                        "JSON array of sections. Each section (all fields optional): "
                        "{\"heading\": str, \"level\": int (1-3, default 1), "
                        "\"text\": str, \"bullets\": [str], "
                        "\"table\": {\"headers\": [str], \"rows\": [[value]]}}. "
                        "Example: [{\"heading\": \"Summary\", \"level\": 1, \"text\": \"Overview text.\", \"bullets\": [\"Item A\"]}]"
                    ),
                },
                "author": {
                    "type": "string",
                    "description": "Author name stored in document metadata (optional)",
                },
            },
            "required": ["filename", "title", "sections"],
        }

    def execute(self, filename: str, title: str, sections: str, author: str = "") -> str:
        self._emit(f"📝 Creating DOCX: '{filename}'...")
        try:
            from docx import Document
            from docx.shared import Pt, RGBColor as DocxRGB, Inches as DocxInches
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.oxml.ns import qn
            from docx.oxml import OxmlElement
        except ImportError:
            return "❌ python-docx not installed. Run: pip install python-docx"

        try:
            section_data: List[dict] = json.loads(sections)
        except json.JSONDecodeError as e:
            return f"❌ Invalid JSON in 'sections': {e}"

        artifacts_dir = _get_artifacts_dir(self.scratchpad)
        out_path = artifacts_dir / _safe_filename(filename)
        if not out_path.suffix:
            out_path = out_path.with_suffix(".docx")

        doc = Document()

        # Document metadata
        core = doc.core_properties
        core.title = title
        if author:
            core.author = author

        # Heading styles tuning
        def _set_heading_color(paragraph, hex_color: str = "1A1A2E"):
            for run in paragraph.runs:
                run.font.color.rgb = DocxRGB(
                    int(hex_color[0:2], 16),
                    int(hex_color[2:4], 16),
                    int(hex_color[4:6], 16),
                )

        # Document title
        title_para = doc.add_heading(title, level=0)
        _set_heading_color(title_para, "1A1A2E")

        if author:
            para = doc.add_paragraph()
            run = para.add_run(f"Author: {author}")
            run.italic = True
            run.font.size = Pt(10)
            run.font.color.rgb = DocxRGB(0x66, 0x66, 0x66)

        doc.add_paragraph()  # spacer

        for sec in section_data:
            level = max(1, min(3, int(sec.get("level", 1))))
            heading = sec.get("heading", "")
            text = sec.get("text", "")
            bullets = sec.get("bullets", [])
            table_data = sec.get("table")

            if heading:
                h = doc.add_heading(heading, level=level)
                _set_heading_color(h, "16213E")

            if text:
                doc.add_paragraph(text)

            for bullet in bullets:
                doc.add_paragraph(bullet, style="List Bullet")

            if table_data and isinstance(table_data, dict):
                headers = table_data.get("headers", [])
                rows = table_data.get("rows", [])
                if headers:
                    num_cols = len(headers)
                    tbl = doc.add_table(rows=1 + len(rows), cols=num_cols)
                    tbl.style = "Table Grid"
                    # Header row
                    header_row = tbl.rows[0]
                    for col_idx, h_text in enumerate(headers):
                        cell = header_row.cells[col_idx]
                        cell.text = str(h_text)
                        run = cell.paragraphs[0].runs[0]
                        run.bold = True
                        run.font.color.rgb = DocxRGB(0xFF, 0xFF, 0xFF)
                        # Background color for header cell
                        tc = cell._tc
                        tcPr = tc.get_or_add_tcPr()
                        shd = OxmlElement("w:shd")
                        shd.set(qn("w:val"), "clear")
                        shd.set(qn("w:color"), "auto")
                        shd.set(qn("w:fill"), "1A1A2E")
                        tcPr.append(shd)
                    # Data rows
                    for row_idx, row in enumerate(rows):
                        tbl_row = tbl.rows[row_idx + 1]
                        for col_idx, val in enumerate(row):
                            if col_idx < num_cols:
                                tbl_row.cells[col_idx].text = str(val)

            doc.add_paragraph()  # spacer between sections

        doc.save(str(out_path))
        size_kb = out_path.stat().st_size // 1024

        return (
            f"✅ DOCX created!\n"
            f"• File: `{out_path.name}`\n"
            f"• Path: `{out_path}`\n"
            f"• Size: {size_kb} KB\n"
            f"• Sections: {len(section_data)}"
        )
