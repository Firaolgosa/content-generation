#!/usr/bin/env python3
"""
Generate REPORT.pdf from REPORT.md using ReportLab.
Usage: python scripts/generate_report_pdf.py
Output: REPORT.pdf in the project root.
"""

from __future__ import annotations
import re
import sys
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        HRFlowable,
        Table,
        TableStyle,
        PageBreak,
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
except ImportError:
    print("reportlab not installed. Run: pip install reportlab")
    sys.exit(1)

# ── paths ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
REPORT_MD = ROOT / "REPORT.md"
OUTPUT_PDF = ROOT / "REPORT.pdf"

# ── colour palette (Ethiopian-inspired earthy tones) ────────────────────────
C_RUST   = colors.HexColor("#8B3A2A")   # warm rust red
C_GOLD   = colors.HexColor("#C8973A")   # ochre gold
C_DARK   = colors.HexColor("#1A1209")   # near-black
C_MID    = colors.HexColor("#4A3728")   # dark brown
C_LIGHT  = colors.HexColor("#FDF6EC")   # parchment
C_RULE   = colors.HexColor("#C8973A")   # horizontal rule
C_CODE_BG = colors.HexColor("#F5EFE6")  # code block background
C_GRAY   = colors.HexColor("#6B5B4E")   # muted text

# ── custom styles ────────────────────────────────────────────────────────────
def build_styles() -> dict:
    base = getSampleStyleSheet()

    styles = {}

    styles["title"] = ParagraphStyle(
        "ReportTitle",
        parent=base["Title"],
        fontSize=22,
        leading=28,
        textColor=C_RUST,
        fontName="Helvetica-Bold",
        spaceAfter=4,
        alignment=TA_LEFT,
    )
    styles["subtitle"] = ParagraphStyle(
        "Subtitle",
        parent=base["Normal"],
        fontSize=11,
        leading=16,
        textColor=C_MID,
        fontName="Helvetica",
        spaceAfter=2,
        alignment=TA_LEFT,
    )
    styles["h1"] = ParagraphStyle(
        "H1",
        parent=base["Heading1"],
        fontSize=14,
        leading=20,
        textColor=C_RUST,
        fontName="Helvetica-Bold",
        spaceBefore=16,
        spaceAfter=4,
    )
    styles["h2"] = ParagraphStyle(
        "H2",
        parent=base["Heading2"],
        fontSize=12,
        leading=16,
        textColor=C_MID,
        fontName="Helvetica-Bold",
        spaceBefore=10,
        spaceAfter=3,
    )
    styles["body"] = ParagraphStyle(
        "Body",
        parent=base["Normal"],
        fontSize=10.5,
        leading=16,
        textColor=C_DARK,
        fontName="Helvetica",
        spaceAfter=6,
        alignment=TA_JUSTIFY,
    )
    styles["bullet"] = ParagraphStyle(
        "Bullet",
        parent=base["Normal"],
        fontSize=10.5,
        leading=15,
        textColor=C_DARK,
        fontName="Helvetica",
        leftIndent=14,
        bulletIndent=0,
        spaceAfter=4,
        bulletText="•",
    )
    styles["sub_bullet"] = ParagraphStyle(
        "SubBullet",
        parent=base["Normal"],
        fontSize=10,
        leading=14,
        textColor=C_MID,
        fontName="Helvetica",
        leftIndent=28,
        bulletIndent=14,
        spaceAfter=3,
        bulletText="–",
    )
    styles["code"] = ParagraphStyle(
        "Code",
        parent=base["Code"],
        fontSize=8.5,
        leading=12,
        textColor=C_DARK,
        fontName="Courier",
        backColor=C_CODE_BG,
        leftIndent=10,
        rightIndent=10,
        spaceBefore=4,
        spaceAfter=4,
    )
    styles["meta"] = ParagraphStyle(
        "Meta",
        parent=base["Normal"],
        fontSize=9,
        leading=13,
        textColor=C_GRAY,
        fontName="Helvetica-Oblique",
        spaceAfter=2,
    )
    styles["hr_space"] = ParagraphStyle("HRSpace", parent=base["Normal"], spaceAfter=0, spaceBefore=0)

    return styles


# ── markdown parser (simple, covers REPORT.md structure) ────────────────────
def md_to_flowables(md_text: str, styles: dict) -> list:
    """Convert a simplified markdown string to a list of ReportLab flowables."""
    flowables: list = []
    lines = md_text.splitlines()
    i = 0
    in_code_block = False
    code_lines: list[str] = []

    def flush_code():
        nonlocal code_lines, in_code_block
        if code_lines:
            text = "\n".join(code_lines)
            flowables.append(Paragraph(text.replace("\n", "<br/>").replace(" ", "&nbsp;"), styles["code"]))
            flowables.append(Spacer(1, 4))
        code_lines = []
        in_code_block = False

    def clean(txt: str) -> str:
        """Escape XML and apply simple inline markdown."""
        txt = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # bold+italic ***
        txt = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", txt)
        # bold **
        txt = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", txt)
        # italic *
        txt = re.sub(r"\*(.+?)\*", r"<i>\1</i>", txt)
        # backtick code
        txt = re.sub(r"`([^`]+)`", r'<font name="Courier" size="9">\1</font>', txt)
        # links [text](url) → text (url) or just text
        txt = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", txt)
        return txt

    while i < len(lines):
        line = lines[i]

        # code blocks
        if line.startswith("```"):
            if in_code_block:
                flush_code()
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # horizontal rule
        if line.strip() in ("---", "***", "___"):
            flowables.append(Spacer(1, 6))
            flowables.append(HRFlowable(width="100%", thickness=1, color=C_RULE, spaceAfter=6))
            i += 1
            continue

        # headings
        m = re.match(r"^(#{1,4})\s+(.+)", line)
        if m:
            level = len(m.group(1))
            text = clean(m.group(2))
            if level == 1:
                flowables.append(Paragraph(text, styles["h1"]))
            elif level == 2:
                flowables.append(Spacer(1, 4))
                flowables.append(Paragraph(text, styles["h2"]))
            else:
                sub = ParagraphStyle(
                    f"H{level}",
                    parent=styles["h2"],
                    fontSize=10.5,
                    textColor=C_MID,
                    fontName="Helvetica-BoldOblique",
                    spaceBefore=6,
                )
                flowables.append(Paragraph(text, sub))
            i += 1
            continue

        # block quotes (treat as italic note)
        if line.startswith(">"):
            inner = clean(line.lstrip("> ").strip())
            note_style = ParagraphStyle(
                "BlockQuote",
                parent=styles["body"],
                fontName="Helvetica-Oblique",
                textColor=C_MID,
                leftIndent=18,
                borderPad=4,
            )
            flowables.append(Paragraph(f"<i>{inner}</i>", note_style))
            i += 1
            continue

        # unordered bullets  - or *
        m_bull = re.match(r"^(\s*)([-*+])\s+(.+)", line)
        if m_bull:
            indent = len(m_bull.group(1))
            text = clean(m_bull.group(3))
            if indent == 0:
                flowables.append(Paragraph(text, styles["bullet"]))
            else:
                flowables.append(Paragraph(text, styles["sub_bullet"]))
            i += 1
            continue

        # numbered lists
        m_num = re.match(r"^\s*\d+\.\s+(.+)", line)
        if m_num:
            text = clean(m_num.group(1))
            num_style = ParagraphStyle(
                "NumList",
                parent=styles["bullet"],
                bulletText=None,
                leftIndent=18,
            )
            flowables.append(Paragraph(text, num_style))
            i += 1
            continue

        # table rows (simple 2–N col tables)
        if "|" in line and line.strip().startswith("|"):
            # collect all table lines
            table_lines = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip().startswith("|"):
                raw = lines[i]
                # skip separator rows like |---|---|
                if re.match(r"^\|[-| :]+\|$", raw.strip()):
                    i += 1
                    continue
                cells = [clean(c.strip()) for c in raw.strip().strip("|").split("|")]
                table_lines.append(cells)
                i += 1
            if table_lines:
                # first row is header
                header = table_lines[0]
                data = table_lines
                col_count = max(len(r) for r in data)
                # pad rows
                data = [r + [""] * (col_count - len(r)) for r in data]
                col_width = (A4[0] - 4 * cm) / col_count
                t = Table(data, colWidths=[col_width] * col_count)
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), C_RUST),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 8.5),
                    ("BACKGROUND", (0, 1), (-1, -1), C_LIGHT),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_LIGHT, colors.white]),
                    ("GRID", (0, 0), (-1, -1), 0.4, C_GOLD),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("WORDWRAP", (0, 0), (-1, -1), True),
                ]))
                flowables.append(Spacer(1, 6))
                flowables.append(t)
                flowables.append(Spacer(1, 6))
            continue

        # blank lines
        if line.strip() == "":
            flowables.append(Spacer(1, 4))
            i += 1
            continue

        # normal paragraph
        text = clean(line.strip())
        if text:
            flowables.append(Paragraph(text, styles["body"]))
        i += 1

    if in_code_block:
        flush_code()

    return flowables


# ── header / footer ──────────────────────────────────────────────────────────
def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4

    # top rule
    canvas.setStrokeColor(C_GOLD)
    canvas.setLineWidth(1.2)
    canvas.line(1.5 * cm, h - 1.2 * cm, w - 1.5 * cm, h - 1.2 * cm)

    # header text
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(C_MID)
    canvas.drawString(1.5 * cm, h - 1.0 * cm, "The Night in Bekoji | B2W0 Engineering Report")
    canvas.drawRightString(w - 1.5 * cm, h - 1.0 * cm, "10 Academy — AI Content Generation")

    # bottom rule + page number
    canvas.setStrokeColor(C_GOLD)
    canvas.line(1.5 * cm, 1.4 * cm, w - 1.5 * cm, 1.4 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(C_MID)
    canvas.drawCentredString(w / 2, 1.0 * cm, f"Page {doc.page}")

    canvas.restoreState()


# ── cover page ───────────────────────────────────────────────────────────────
def cover_page(styles: dict) -> list:
    flowables = []
    w, h = A4

    flowables.append(Spacer(1, 2.5 * cm))

    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["title"],
        fontSize=28,
        leading=36,
        alignment=TA_CENTER,
        textColor=C_RUST,
        spaceAfter=8,
    )
    sub_style = ParagraphStyle(
        "CoverSub",
        parent=styles["subtitle"],
        fontSize=14,
        leading=20,
        alignment=TA_CENTER,
        textColor=C_GOLD,
        spaceAfter=6,
    )
    meta_style = ParagraphStyle(
        "CoverMeta",
        parent=styles["meta"],
        fontSize=11,
        alignment=TA_CENTER,
        textColor=C_MID,
        spaceAfter=4,
    )

    flowables.append(Paragraph("The Night in Bekoji", title_style))
    flowables.append(Paragraph("የበቆጂው ምሽት", sub_style))
    flowables.append(Spacer(1, 0.6 * cm))
    flowables.append(HRFlowable(width="60%", thickness=1.5, color=C_GOLD, hAlign="CENTER", spaceAfter=10))
    flowables.append(Spacer(1, 0.4 * cm))

    flowables.append(Paragraph("Engineering Report", meta_style))
    flowables.append(Paragraph("B2W0: AI-Content Generation — Codebase and Report", meta_style))
    flowables.append(Spacer(1, 1.0 * cm))

    # info table
    info_data = [
        ["Programme", "10 Academy — Week 0 Challenge"],
        ["Submission Deadline", "26 November 2026, 23:59 EAT"],
        ["Film Duration", "75 seconds | −14 LUFS"],
        ["Aspect Ratios", "16:9 (landscape) + 9:16 (vertical/mobile)"],
        ["Narration", "Amharic (Sulafat TTS) + English subtitles"],
        ["Total API Cost", "$0.0351 list price / $0 actual (free tiers)"],
        ["Tests", "59 passed | ruff: all checks passed"],
    ]
    info_style = TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), C_RUST),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (1, 0), (1, -1), C_LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.5, C_GOLD),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ])
    t = Table(info_data, colWidths=[5 * cm, 10 * cm])
    t.setStyle(info_style)
    flowables.append(t)
    flowables.append(Spacer(1, 1.2 * cm))

    flowables.append(HRFlowable(width="60%", thickness=1.5, color=C_GOLD, hAlign="CENTER", spaceAfter=14))
    flowables.append(Paragraph(
        "A fully automated AI film pipeline built with Gemini TTS, Cloudflare Workers AI (FLUX), "
        "Wan 2.2 TI2V-5B on Kaggle, and ACE-Step 1.5 — rendering a true Ethiopian family heritage "
        "story set in 1950 E.C. Bekoji.",
        ParagraphStyle("CoverBlurb", parent=styles["body"], alignment=TA_CENTER, textColor=C_MID, fontSize=10)
    ))

    flowables.append(PageBreak())
    return flowables


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    md_text = REPORT_MD.read_text(encoding="utf-8")
    styles = build_styles()

    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title="The Night in Bekoji — Engineering Report",
        author="10 Academy B2W0",
        subject="AI-Content Generation Codebase and Report",
    )

    story: list = []

    # cover
    story.extend(cover_page(styles))

    # table of contents (manual)
    toc_style = ParagraphStyle("TOC", parent=styles["body"], fontSize=10.5, spaceAfter=5)
    toc_title = ParagraphStyle("TOCTitle", parent=styles["h1"], fontSize=14)
    story.append(Paragraph("Table of Contents", toc_title))
    story.append(HRFlowable(width="100%", thickness=0.6, color=C_GOLD, spaceAfter=8))
    sections = [
        "1. What We Set Out to Make and For Whom",
        "2. Pipeline Architecture & Reproducibility",
        "3. What We Learned From Our Audience",
        "4. The Hardest Problem and How We Solved It",
        "5. Suggested Practices Tested Honestly",
        "6. Ceiling Work & What We Would Build Next",
    ]
    for s in sections:
        story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;{s}", toc_style))
    story.append(PageBreak())

    # body from REPORT.md (skip the YAML front-matter title block at top since cover handles it)
    # strip the top 4-line header (# title + **Assignment** + **Repository** + **Film Outputs** + ---)
    body_lines = md_text.splitlines()
    # find first ## heading and start from there
    start = 0
    for idx, l in enumerate(body_lines):
        if l.startswith("## "):
            start = idx
            break
    body_md = "\n".join(body_lines[start:])

    story.extend(md_to_flowables(body_md, styles))

    # build
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    print(f"✅  Report saved to: {OUTPUT_PDF}")
    size_kb = OUTPUT_PDF.stat().st_size // 1024
    print(f"    Size: {size_kb} KB")


if __name__ == "__main__":
    main()
