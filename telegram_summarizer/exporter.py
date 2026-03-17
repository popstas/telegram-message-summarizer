import io
import os
import re

from docx import Document
from fpdf import FPDF

_DEJAVU_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def export_markdown(summary_text: str) -> str:
    return summary_text


def _setup_pdf_fonts(pdf: FPDF) -> str:
    """Set up fonts, return font family name to use."""
    if os.path.exists(_DEJAVU_REGULAR) and os.path.exists(_DEJAVU_BOLD):
        pdf.add_font("DejaVu", "", _DEJAVU_REGULAR)
        pdf.add_font("DejaVu", "B", _DEJAVU_BOLD)
        return "DejaVu"
    return "Helvetica"


def export_pdf(summary_text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    font_family = _setup_pdf_fonts(pdf)
    pdf.set_font(font_family, size=11)
    pdf.set_auto_page_break(auto=True, margin=15)

    w = pdf.epw
    for line in summary_text.split("\n"):
        if re.match(r"^#{1,3}\s", line):
            pdf.set_font(font_family, "B", size=14)
            pdf.multi_cell(w, 8, line.lstrip("# ").strip())
            pdf.set_font(font_family, size=11)
        elif line.strip() == "":
            pdf.ln(4)
        else:
            pdf.multi_cell(w, 8, line)

    return bytes(pdf.output())


def export_docx(summary_text: str) -> bytes:
    doc = Document()

    for line in summary_text.split("\n"):
        if re.match(r"^#{1,3}\s", line):
            level = len(line) - len(line.lstrip("#"))
            doc.add_heading(line.lstrip("# ").strip(), level=min(level, 9))
        elif line.strip() == "":
            continue
        else:
            doc.add_paragraph(line)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
