import io
import os
import re

from docx import Document
from fpdf import FPDF

_DEJAVU_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def export_markdown(summary_text: str) -> str:
    return summary_text


# Characters that must be escaped in Telegram MarkdownV2
_TLG_SPECIAL = r"_*[]()~`>#+\-=|{}.!"


def _escape_tlg(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    result = []
    for ch in text:
        if ch in _TLG_SPECIAL:
            result.append("\\")
        result.append(ch)
    return "".join(result)


def export_tlg(summary_text: str) -> str:
    """Convert standard markdown to Telegram MarkdownV2 format."""
    lines = summary_text.split("\n")
    out = []
    for line in lines:
        # Convert headings: # Heading → *Heading*
        heading_match = re.match(r"^(#{1,3})\s+(.*)", line)
        if heading_match:
            heading_text = _escape_tlg(heading_match.group(2).strip())
            out.append(f"*{heading_text}*")
            continue

        # Convert bold: **text** → *text*
        # Process bold markers before escaping the rest
        parts = re.split(r"\*\*(.+?)\*\*", line)
        converted = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                # This is bold content
                converted.append(f"*{_escape_tlg(part)}*")
            else:
                # Convert bullet lists: - item → • item
                bullet_match = re.match(r"^(\s*)-\s+(.*)", part)
                if bullet_match and i == 0:
                    indent = bullet_match.group(1)
                    rest = _escape_tlg(bullet_match.group(2))
                    converted.append(f"{indent}• {rest}")
                else:
                    converted.append(_escape_tlg(part))
        out.append("".join(converted))

    return "\n".join(out)


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
            pdf.multi_cell(w, 8, re.sub(r"^#{1,3}\s+", "", line).strip())
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
            doc.add_heading(re.sub(r"^#{1,3}\s+", "", line).strip(), level=min(level, 9))
        elif line.strip() == "":
            continue
        else:
            doc.add_paragraph(line)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
