"""Operational visual pages for deterministic exercise reports."""

from hashlib import sha256
from textwrap import wrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from coeus.domain.store import StoreProduct

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 54
NAVY = colors.HexColor("#0A1724")
BLUE = colors.HexColor("#2F8CFF")
PALE = colors.HexColor("#EAF3FF")
INK = colors.HexColor("#172433")
MUTED = colors.HexColor("#526579")
GRID = colors.HexColor("#B7C9D8")
TOTAL_PAGES = 8


def draw_operational_pages(pdf: Canvas, product: StoreProduct, marker: str) -> None:
    _situation_map(pdf, product, marker)
    _daily_timeline(pdf, product, marker)
    _translated_extracts(pdf, product, marker)
    _multi_source_assessment(pdf, product, marker)


def _situation_map(pdf: Canvas, product: StoreProduct, marker: str) -> None:
    _header(pdf, product, marker, "Situation map and imagery review", 3)
    x, y, width, height = MARGIN, 365, PAGE_WIDTH - 2 * MARGIN, 315
    pdf.setFillColor(colors.HexColor("#F4F8FB"))
    pdf.setStrokeColor(GRID)
    pdf.rect(x, y, width, height, fill=1, stroke=1)
    for step in range(1, 6):
        pdf.line(x + width * step / 6, y, x + width * step / 6, y + height)
    for step in range(1, 5):
        pdf.line(x, y + height * step / 5, x + width, y + height * step / 5)
    pdf.setStrokeColor(BLUE)
    pdf.setLineWidth(3)
    pdf.bezier(x + 25, y + 55, x + 155, y + 180, x + 320, y + 80, x + 445, y + 245)
    points = _map_points(product, x, y, width, height)
    for index, (point_x, point_y) in enumerate(points, start=1):
        pdf.setFillColor(colors.HexColor("#E2534A") if index == 3 else BLUE)
        pdf.circle(point_x, point_y, 7, fill=1, stroke=0)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(point_x + 10, point_y + 2, f"AOI-{index}")
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(x + 8, y + 8, "Schematic exercise grid. Coordinates are deliberately omitted.")
    _section(pdf, "Imagery interpretation", 330)
    captions = (
        "AOI-1: notional vehicle concentration increased across two review periods.",
        "AOI-2: simulated route activity aligns with the daily reporting timeline.",
        "AOI-3: apparent change may reflect weather, maintenance or collection bias.",
    )
    for index, caption in enumerate(captions):
        box_x = MARGIN + index * 162
        pdf.setFillColor(PALE)
        pdf.roundRect(box_x, 125, 148, 155, 6, fill=1, stroke=0)
        pdf.setFillColor(NAVY)
        pdf.rect(box_x + 10, 205, 128, 60, fill=1, stroke=0)
        pdf.setStrokeColor(colors.HexColor("#6586A3"))
        for offset in range(0, 128, 16):
            pdf.line(box_x + 10 + offset, 205, box_x + 35 + offset, 265)
        pdf.setFillColor(INK)
        _wrapped(pdf, caption, box_x + 10, 190, 8.5, 12, 25)
    _footer(pdf, product, 3)
    pdf.showPage()


def _daily_timeline(pdf: Canvas, product: StoreProduct, marker: str) -> None:
    _header(pdf, product, marker, "Seven-day activity timeline", 4)
    themes = _themes(product)
    y: float = 665
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(MARGIN, y, "Daily summary derived from invented exercise reporting only.")
    y -= 32
    widths = (55, 120, 235, 70)
    _table_row(pdf, y, widths, ("Day", "Primary feed", "Daily summary", "Confidence"), True)
    y -= 34
    feeds = ("Imagery", "Signals", "Open source", "Human report")
    confidence = ("Low", "Moderate", "Moderate", "High", "Low", "Moderate", "Moderate")
    for day in range(1, 8):
        theme = themes[(day - 1) % len(themes)]
        summary = (
            f"Synthetic reporting notes {theme} activity and one collection gap in the "
            f"{product.metadata.area_or_region} exercise area."
        )
        _table_row(
            pdf,
            y,
            widths,
            (f"D{day}", feeds[(day - 1) % len(feeds)], summary, confidence[day - 1]),
            False,
            height=56,
        )
        y -= 56
    _section(pdf, "Timeline judgement", 176)
    _wrapped(
        pdf,
        "The sequence is consistent with a notional readiness cycle, but the exercise record "
        "cannot distinguish preparation from routine training or reporting artefacts.",
        MARGIN,
        151,
        10,
        15,
        92,
    )
    _footer(pdf, product, 4)
    pdf.showPage()


def _translated_extracts(pdf: Canvas, product: StoreProduct, marker: str) -> None:
    _header(pdf, product, marker, "Translated reporting extracts", 5)
    themes = _themes(product)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(MARGIN, 665, "Invented transliterations and translations for workflow testing.")
    cards = (
        (
            "Local bulletin",
            f"Uchebnyy signal: {themes[0]} aktivnost vozrosla.",
            f"Exercise signal: {themes[0]} activity increased.",
        ),
        (
            "Field note",
            f"Nablyudenie: {themes[1]} peremeshchenie ogranicheno.",
            f"Observation: {themes[1]} movement was limited.",
        ),
        (
            "Technical log",
            f"Kontrol: {themes[2]} proverka ne zavershena.",
            f"Control note: the {themes[2]} check is incomplete.",
        ),
    )
    y = 610
    for index, (source, original, translation) in enumerate(cards, start=1):
        pdf.setFillColor(PALE)
        pdf.roundRect(MARGIN, y - 132, PAGE_WIDTH - 2 * MARGIN, 132, 8, fill=1, stroke=0)
        pdf.setFillColor(BLUE)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(MARGIN + 16, y - 24, f"EXTRACT {index} | {source.upper()}")
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Oblique", 10)
        _wrapped(pdf, original, MARGIN + 16, y - 50, 10, 14, 84)
        pdf.setFont("Helvetica", 10)
        _wrapped(pdf, f"Analyst translation: {translation}", MARGIN + 16, y - 85, 10, 14, 84)
        y -= 158
    _section(pdf, "Translation caveat", 130)
    _wrapped(
        pdf,
        "All wording is fictional and romanised to avoid implying a real intercepted source. "
        "Translation confidence is part of the exercise, not a linguistic assessment.",
        MARGIN,
        106,
        10,
        15,
        92,
    )
    _footer(pdf, product, 5)
    pdf.showPage()


def _multi_source_assessment(pdf: Canvas, product: StoreProduct, marker: str) -> None:
    _header(pdf, product, marker, "Multi-source assessment", 6)
    y: float = 665
    widths = (82, 125, 155, 118)
    _table_row(pdf, y, widths, ("Source", "Contribution", "Consistency", "Gap"), True)
    y -= 34
    rows = (
        ("GEOINT", "Change detection", "Supports timing", "No unit identity"),
        ("SIGINT", "Activity pattern", "Partly corroborates", "No parameters"),
        ("OSINT", "Context and claims", "Mixed reliability", "Source recycling"),
        ("HUMINT", "Intent hypothesis", "Single-source only", "No validation"),
        ("Technical", "Readiness indicators", "Supports tempo", "Coverage uneven"),
    )
    for row in rows:
        _table_row(pdf, y, widths, row, False)
        y -= 66
    _section(pdf, "All-source judgement", 280)
    _wrapped(
        pdf,
        "The fictional sources support a moderate-confidence assessment of changing exercise "
        "tempo. They do not support attribution, operational intent or precise location. "
        "Contradictions remain visible and should drive follow-on collection questions.",
        MARGIN,
        254,
        10.5,
        16,
        90,
    )
    _section(pdf, "Priority collection questions", 185)
    questions = (
        "Can later imagery distinguish movement from routine dispersal?",
        "Do independent sources corroborate the timing and direction of activity?",
        "Which assumptions would change the confidence judgement most?",
    )
    y = 158.0
    for question in questions:
        pdf.setFillColor(BLUE)
        pdf.circle(MARGIN + 4, y - 4, 2.5, fill=1, stroke=0)
        pdf.setFillColor(INK)
        y = _wrapped(pdf, question, MARGIN + 16, y, 10, 14, 86) - 7
    _footer(pdf, product, 6)
    pdf.showPage()


def _header(pdf: Canvas, product: StoreProduct, marker: str, title: str, page: int) -> None:
    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
    pdf.setFillColor(NAVY)
    pdf.rect(0, PAGE_HEIGHT - 78, PAGE_WIDTH, 78, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(MARGIN, PAGE_HEIGHT - 32, marker)
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(
        PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 32, f"{product.reference} | {page}/{TOTAL_PAGES}"
    )
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(MARGIN, PAGE_HEIGHT - 104, title)


def _footer(pdf: Canvas, product: StoreProduct, page: int) -> None:
    pdf.setStrokeColor(colors.HexColor("#CAD6E2"))
    pdf.line(MARGIN, 42, PAGE_WIDTH - MARGIN, 42)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(MARGIN, 27, "ISTARI EXERCISE LIBRARY")
    pdf.drawRightString(PAGE_WIDTH - MARGIN, 27, f"{product.reference} | Page {page} of 8")


def _section(pdf: Canvas, heading: str, y: float) -> None:
    pdf.setFillColor(BLUE)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(MARGIN, y, heading.upper())


def _wrapped(
    pdf: Canvas, text: str, x: float, y: float, size: float, leading: float, width: int
) -> float:
    pdf.setFont("Helvetica", size)
    for line in wrap(text, width=width):
        pdf.drawString(x, y, line)
        y -= leading
    return y


def _table_row(
    pdf: Canvas,
    y: float,
    widths: tuple[int, int, int, int],
    values: tuple[str, str, str, str],
    header: bool,
    *,
    height: int | None = None,
) -> None:
    row_height = height if height is not None else (34 if header else 61)
    x = MARGIN
    pdf.setFillColor(NAVY if header else colors.white)
    pdf.setStrokeColor(colors.HexColor("#CAD6E2"))
    pdf.rect(x, y - row_height, sum(widths), row_height, fill=1, stroke=1)
    for index, (width, value) in enumerate(zip(widths, values, strict=True)):
        if index:
            pdf.line(x, y - row_height, x, y)
        pdf.setFillColor(colors.white if header else INK)
        pdf.setFont("Helvetica-Bold" if header else "Helvetica", 8.5)
        leading = 10.5 if row_height < 61 else 12
        for line_index, line in enumerate(wrap(value, width=max(9, int(width / 5.8)))[:4]):
            pdf.drawString(x + 7, y - 18 - line_index * leading, line)
        x += width


def _map_points(
    product: StoreProduct, x: float, y: float, width: float, height: float
) -> tuple[tuple[float, float], ...]:
    digest = sha256(str(product.product_id).encode()).digest()
    return tuple(
        (
            x + 45 + (digest[index] / 255) * (width - 90),
            y + 45 + (digest[index + 3] / 255) * (height - 90),
        )
        for index in range(3)
    )


def _themes(product: StoreProduct) -> tuple[str, str, str]:
    ignored = {"mock-data", "synthetic-exercise", "synthetic-conflict"}
    values = list(
        dict.fromkeys(tag.replace("-", " ") for tag in sorted(product.metadata.tags - ignored))
    )
    values.extend(value for value in ("activity", "readiness", "warning") if value not in values)
    return values[0], values[1], values[2]
