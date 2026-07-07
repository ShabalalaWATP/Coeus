from pathlib import Path
from textwrap import wrap
from zipfile import ZIP_DEFLATED, ZipFile

from .models import MOCK_BANNER, SeedProduct

DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)
OFFICE_DOCUMENT_RELATIONSHIP = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)


def write_pdf(path: Path, product: SeedProduct) -> None:
    _ensure_parent(path)
    stream = _pdf_stream(product)
    body = (
        "%PDF-1.4\n"
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        f"5 0 obj << /Length {len(stream)} >> stream\n{stream}\nendstream endobj\n"
        "xref\n0 6\n0000000000 65535 f \n"
        "trailer << /Root 1 0 R /Size 6 >>\nstartxref\n0\n%%EOF\n"
    )
    path.write_bytes(body.encode())


def write_docx(path: Path, product: SeedProduct) -> None:
    _ensure_parent(path)
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{MOCK_BANNER}</w:t></w:r></w:p>
    <w:p><w:r><w:t>{product.title}</w:t></w:r></w:p>
    <w:p><w:r><w:t>{product.summary}</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _relationships_xml())
        archive.writestr("word/document.xml", document)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _content_types_xml() -> str:
    return "\n".join(
        (
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
            (
                '  <Default Extension="rels" '
                'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            ),
            '  <Default Extension="xml" ContentType="application/xml"/>',
            (f'  <Override PartName="/word/document.xml" ContentType="{DOCX_CONTENT_TYPE}"/>'),
            "</Types>",
        )
    )


def _relationships_xml() -> str:
    return "\n".join(
        (
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
            (
                '  <Relationship Id="rId1" '
                f'Type="{OFFICE_DOCUMENT_RELATIONSHIP}" Target="word/document.xml"/>'
            ),
            "</Relationships>",
        )
    )


def _pdf_stream(product: SeedProduct) -> str:
    lines = [
        MOCK_BANNER,
        product.title,
        product.summary,
        product.description,
        f"Tags: {', '.join(product.tags)}",
        f"Semantic labels: {', '.join(product.semantic_labels)}",
        f"Coverage: {product.time_period_start} to {product.time_period_end}",
    ]
    wrapped = [part for line in lines for part in wrap(line, width=72)]
    commands = ["BT /F1 13 Tf 72 760 Td 17 TL"]
    commands.extend(f"({_escape_pdf_text(line)}) Tj T*" for line in wrapped[:38])
    commands.append("ET")
    return "\n".join(commands)


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
