"""Deterministic four-page PDFs for the synthetic local demo Store."""

from io import BytesIO
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
MOCK_BANNER = "MOCK DATA ONLY - SYNTHETIC EXERCISE PRODUCT"


def build_demo_pdf_bytes(product: StoreProduct) -> bytes:
    buffer = BytesIO()
    pdf = Canvas(
        buffer,
        pagesize=A4,
        pageCompression=1,
        invariant=1,
    )
    pdf.setAuthor("Coeus synthetic data generator")
    pdf.setCreator("Coeus local demo")
    pdf.setTitle(product.metadata.title)
    _cover(pdf, product)
    _executive_summary(pdf, product)
    _indicator_matrix(pdf, product)
    _assessment(pdf, product)
    pdf.save()
    return buffer.getvalue()


def _cover(pdf: Canvas, product: StoreProduct) -> None:
    metadata = product.metadata
    pdf.setFillColor(NAVY)
    pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
    pdf.setFillColor(BLUE)
    pdf.rect(0, PAGE_HEIGHT - 16, PAGE_WIDTH, 16, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(MARGIN, PAGE_HEIGHT - 62, "COEUS SYNTHETIC INTELLIGENCE LIBRARY")
    y = PAGE_HEIGHT - 145
    y = _draw_wrapped(pdf, metadata.title, MARGIN, y, 26, 30, 33, "Helvetica-Bold")
    pdf.setFillColor(PALE)
    y -= 20
    y = _draw_wrapped(pdf, metadata.summary, MARGIN, y, 13, 19, 72, "Helvetica")
    y -= 38
    _metadata_card(pdf, product, y)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(MARGIN, 82, MOCK_BANNER)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(
        MARGIN, 62, "Contains no real reporting, units, sources or operational locations."
    )
    _footer(pdf, product, 1, dark=True)
    pdf.showPage()


def _executive_summary(pdf: Canvas, product: StoreProduct) -> None:
    metadata = product.metadata
    _page_header(pdf, product, "Executive summary", 2)
    y = PAGE_HEIGHT - 115
    y = _section(pdf, "Purpose", y)
    y = _paragraph(pdf, metadata.description, y)
    y -= 8
    y = _section(pdf, "Key judgements", y)
    for judgement in _judgements(product):
        y = _bullet(pdf, judgement, y)
    y -= 8
    y = _section(pdf, "Confidence statement", y)
    _confidence_card(pdf, y)
    _footer(pdf, product, 2)
    pdf.showPage()


def _indicator_matrix(pdf: Canvas, product: StoreProduct) -> None:
    _page_header(pdf, product, "Synthetic indicator matrix", 3)
    y = PAGE_HEIGHT - 122
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(MARGIN, y, "All observations below are invented for software demonstration.")
    y -= 30
    widths = (150, 235, 85)
    headings = ("Theme", "Synthetic observation", "Confidence")
    _table_row(pdf, y, widths, headings, header=True)
    y -= 32
    tags = sorted(product.metadata.tags)
    for index in range(6):
        theme = tags[index % len(tags)].replace("-", " ").title()
        observation = _indicator_observation(theme, index)
        confidence = ("Moderate", "Low", "Moderate", "High", "Low", "Moderate")[index]
        _table_row(pdf, y, widths, (theme, observation, confidence))
        y -= 58
    y -= 18
    y = _section(pdf, "Analytic caution", y)
    _paragraph(
        pdf,
        "No row represents a real event. Apparent correlations are deliberately synthetic and "
        "must not be used for operational planning or external reporting.",
        y,
    )
    _footer(pdf, product, 3)
    pdf.showPage()


def _assessment(pdf: Canvas, product: StoreProduct) -> None:
    _page_header(pdf, product, "Assessment and collection gaps", 4)
    y = PAGE_HEIGHT - 118
    sections = (
        (
            "Assessment",
            "The fictional pattern suggests a training-cycle emphasis on integration, readiness "
            "and command-and-control resilience. Alternative explanations remain deliberately "
            "plausible because this product is designed to exercise analytic comparison.",
        ),
        (
            "Implications",
            "A synthetic customer could use this product to frame follow-on questions about force "
            "protection, logistics, spectrum management and decision timelines. It does not "
            "support a real-world judgement.",
        ),
        (
            "Collection gaps",
            "The exercise record intentionally lacks verified unit identity, precise location, "
            "source provenance and technical parameters. Analysts should state these gaps before "
            "using the mock assessment in a workflow.",
        ),
        (
            "Methodology",
            "Coeus generated this document deterministically from public-repository-safe source "
            "specifications. Searchable metadata mirrors the document themes. No external data, "
            "network source or generative model contributed to the content.",
        ),
    )
    for heading, body in sections:
        y = _section(pdf, heading, y)
        y = _paragraph(pdf, body, y)
        y -= 16
    pdf.setFillColor(PALE)
    pdf.roundRect(MARGIN, 105, PAGE_WIDTH - 2 * MARGIN, 82, 8, fill=1, stroke=0)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(MARGIN + 16, 165, "Handling")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(MARGIN + 16, 144, "MOCK releasability. Synthetic exercise use only.")
    pdf.drawString(
        MARGIN + 16, 125, "Do not interpret as reporting about any real country or organisation."
    )
    _footer(pdf, product, 4)
    pdf.showPage()


def _metadata_card(pdf: Canvas, product: StoreProduct, y: float) -> None:
    metadata = product.metadata
    card_height = 180
    pdf.setFillColor(colors.HexColor("#11283D"))
    pdf.roundRect(
        MARGIN, y - card_height, PAGE_WIDTH - 2 * MARGIN, card_height, 10, fill=1, stroke=0
    )
    fields = (
        ("Reference", product.reference),
        ("Coverage", f"{metadata.time_period_start} to {metadata.time_period_end}"),
        ("Region", metadata.area_or_region),
        ("Product", metadata.product_type.replace("_", " ").title()),
        ("Owner", metadata.owner_team),
        ("ACGs", str(len(metadata.acg_ids))),
    )
    for index, (label, value) in enumerate(fields):
        column = index % 2
        row = index // 2
        x = MARGIN + 18 + column * 244
        row_y = y - 30 - row * 49
        pdf.setFillColor(BLUE)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(x, row_y, label.upper())
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(x, row_y - 17, value[:37])


def _page_header(pdf: Canvas, product: StoreProduct, title: str, page: int) -> None:
    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
    pdf.setFillColor(NAVY)
    pdf.rect(0, PAGE_HEIGHT - 78, PAGE_WIDTH, 78, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(MARGIN, PAGE_HEIGHT - 32, MOCK_BANNER)
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 32, f"{product.reference} | {page}/4")
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(MARGIN, PAGE_HEIGHT - 104, title)


def _footer(pdf: Canvas, product: StoreProduct, page: int, *, dark: bool = False) -> None:
    pdf.setStrokeColor(colors.HexColor("#35506A") if dark else colors.HexColor("#CAD6E2"))
    pdf.line(MARGIN, 42, PAGE_WIDTH - MARGIN, 42)
    pdf.setFillColor(colors.white if dark else MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(MARGIN, 27, MOCK_BANNER)
    pdf.drawRightString(PAGE_WIDTH - MARGIN, 27, f"{product.reference} | Page {page} of 4")


def _section(pdf: Canvas, heading: str, y: float) -> float:
    pdf.setFillColor(BLUE)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(MARGIN, y, heading.upper())
    return y - 24


def _paragraph(pdf: Canvas, text: str, y: float) -> float:
    pdf.setFillColor(INK)
    return _draw_wrapped(pdf, text, MARGIN, y, 10.5, 15, 92, "Helvetica")


def _bullet(pdf: Canvas, text: str, y: float) -> float:
    pdf.setFillColor(BLUE)
    pdf.circle(MARGIN + 4, y - 4, 2.5, fill=1, stroke=0)
    pdf.setFillColor(INK)
    return _draw_wrapped(pdf, text, MARGIN + 16, y, 10.5, 15, 88, "Helvetica") - 8


def _draw_wrapped(
    pdf: Canvas,
    text: str,
    x: float,
    y: float,
    size: float,
    leading: float,
    width: int,
    font: str,
) -> float:
    pdf.setFont(font, size)
    for line in wrap(text, width=width):
        pdf.drawString(x, y, line)
        y -= leading
    return y


def _confidence_card(pdf: Canvas, y: float) -> None:
    pdf.setFillColor(PALE)
    pdf.roundRect(MARGIN, y - 82, PAGE_WIDTH - 2 * MARGIN, 82, 8, fill=1, stroke=0)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(MARGIN + 18, y - 28, "MODERATE - SYNTHETIC")
    pdf.setFont("Helvetica", 9.5)
    pdf.drawString(
        MARGIN + 18, y - 51, "Confidence reflects exercise completeness, not real evidence."
    )


def _table_row(
    pdf: Canvas,
    y: float,
    widths: tuple[int, int, int],
    values: tuple[str, str, str],
    *,
    header: bool = False,
) -> None:
    height = 32 if header else 58
    x = MARGIN
    pdf.setFillColor(NAVY if header else colors.white)
    pdf.setStrokeColor(colors.HexColor("#CAD6E2"))
    pdf.rect(x, y - height, sum(widths), height, fill=1, stroke=1)
    for index, (width, value) in enumerate(zip(widths, values, strict=True)):
        if index:
            pdf.line(x, y - height, x, y)
        pdf.setFillColor(colors.white if header else INK)
        pdf.setFont("Helvetica-Bold" if header else "Helvetica", 8.5)
        max_chars = max(10, int(width / 5.8))
        lines = wrap(value, width=max_chars)[:3]
        for line_index, line in enumerate(lines):
            pdf.drawString(x + 8, y - 19 - line_index * 13, line)
        x += width


def _judgements(product: StoreProduct) -> tuple[str, ...]:
    metadata = product.metadata
    themes = sorted(metadata.tags - {"mock-data", "synthetic-exercise"})
    primary = themes[0].replace("-", " ") if themes else "capability"
    secondary = themes[1].replace("-", " ") if len(themes) > 1 else "readiness"
    return (
        f"The fictional exercise pattern places {primary} activity inside a bounded "
        "training cycle.",
        f"Synthetic indicators suggest {secondary} integration is uneven but improving.",
        "No indicator is independently verified; alternative explanations remain "
        "equally plausible.",
        "Any follow-on tasking should preserve the ACG boundary and restate the mock-data caveat.",
    )


def _indicator_observation(theme: str, index: int) -> str:
    observations = (
        "Exercise reporting shows a fictional increase in scheduled activity.",
        "Synthetic logs suggest coordination across two mock capability areas.",
        "A simulated readiness check records mixed equipment availability.",
        "Invented communications traffic rises during a training window.",
        "A mock logistics note identifies a deliberately unresolved dependency.",
        "Fictional after-action reporting recommends further collection.",
    )
    return f"{observations[index]} Theme: {theme.casefold()}."
