from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from docx import Document
from reportlab.pdfgen.canvas import Canvas

from coeus.core.errors import AppError
from coeus.services import product_processing
from coeus.services.product_processing import process_product_file


def _write(tmp_path, name: str, content: bytes):
    path = tmp_path / name
    path.write_bytes(content)
    return path


def _docx(text: str) -> bytes:
    stream = BytesIO()
    document = Document()
    document.add_paragraph(text)
    document.save(stream)
    return stream.getvalue()


def _zip(**members: bytes) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return stream.getvalue()


@pytest.mark.parametrize(
    ("name", "content", "mime_type", "asset_type"),
    [
        ("map.png", b"\x89PNG\r\n\x1a\nsynthetic", "image/png", "png"),
        ("map.jpeg", b"\xff\xd8\xffsynthetic", "image/jpeg", "jpeg"),
        ("map.webp", b"RIFF0000WEBPsynthetic", "image/webp", "webp"),
    ],
)
def test_accepts_safe_raster_signatures(tmp_path, name, content, mime_type, asset_type) -> None:
    processed = process_product_file(
        _write(tmp_path, name, content), name, hosted_environment=False
    )

    assert processed.detected_mime_type == mime_type
    assert processed.asset_type == asset_type
    assert processed.preview_kind == "image"
    assert processed.extracted_text == ""


def test_extracts_docx_and_bounds_qc_text(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    content = _docx("MOCK DATA ONLY synthetic assessment text")
    monkeypatch.setattr(product_processing, "MAX_QC_TEXT_CHARACTERS", 20)

    processed = process_product_file(
        _write(tmp_path, "report.docx", content), "report.docx", hosted_environment=False
    )

    assert processed.detected_mime_type.endswith("wordprocessingml.document")
    assert processed.preview_kind == "text"
    assert len(processed.extracted_text) == 20


def test_accepts_text_pdf_and_rejects_blank_pdf(tmp_path) -> None:
    text_stream = BytesIO()
    canvas = Canvas(text_stream)
    canvas.drawString(72, 720, "MOCK DATA ONLY synthetic assessment")
    canvas.save()
    processed = process_product_file(
        _write(tmp_path, "report.pdf", text_stream.getvalue()),
        "report.pdf",
        hosted_environment=False,
    )

    blank_stream = BytesIO()
    canvas = Canvas(blank_stream)
    canvas.showPage()
    canvas.save()
    with pytest.raises(AppError, match="document_text_missing"):
        process_product_file(
            _write(tmp_path, "blank.pdf", blank_stream.getvalue()),
            "blank.pdf",
            hosted_environment=False,
        )

    assert processed.preview_kind == "pdf"
    assert "synthetic assessment" in processed.extracted_text


@pytest.mark.parametrize(
    ("name", "content", "code"),
    [
        ("map.jpg", b"\x89PNG\r\n\x1a\nsynthetic", "asset_type_mismatch"),
        ("asset.bin", b"plain bytes", "asset_type_unsupported"),
        ("bad.docx", b"PKnot-a-zip", "office_archive_invalid"),
        ("sheet.docx", _zip(**{"xl/workbook.xml": b"<workbook />"}), "asset_type_unsupported"),
        (
            "macro.docx",
            _zip(
                **{
                    "word/document.xml": b"<document />",
                    "word/vbaProject.bin": b"macro",
                }
            ),
            "office_macros_rejected",
        ),
        (
            "linked.docx",
            _zip(
                **{
                    "word/document.xml": b"<document />",
                    "word/_rels/document.xml.rels": b'<Relationship TargetMode="External" />',
                }
            ),
            "office_external_content_rejected",
        ),
    ],
)
def test_rejects_spoofed_or_unsafe_products(tmp_path, name, content, code) -> None:
    with pytest.raises(AppError, match=code):
        process_product_file(_write(tmp_path, name, content), name, hosted_environment=False)


def test_rejects_office_archives_before_unbounded_name_or_relationship_reads(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = _zip(
        **{
            "word/document.xml": b"<document />",
            "word/_rels/document.xml.rels": b" " * 128,
        }
    )
    monkeypatch.setattr(product_processing, "MAX_OFFICE_ZIP_MEMBERS", 1)
    with pytest.raises(AppError, match="office_archive_too_large"):
        process_product_file(
            _write(tmp_path, "many.docx", content), "many.docx", hosted_environment=False
        )

    monkeypatch.setattr(product_processing, "MAX_OFFICE_ZIP_MEMBERS", 5_000)
    monkeypatch.setattr(product_processing, "MAX_RELATIONSHIP_BYTES", 16)
    with pytest.raises(AppError, match="office_archive_too_large"):
        process_product_file(
            _write(tmp_path, "large-rel.docx", content), "large-rel.docx", hosted_environment=False
        )


def test_fails_closed_without_hosted_malware_scanner_and_rejects_eicar(tmp_path) -> None:
    safe = b"\x89PNG\r\n\x1a\nsynthetic"
    with pytest.raises(AppError, match="malware_scanner_unavailable"):
        process_product_file(
            _write(tmp_path, "safe.png", safe), "safe.png", hosted_environment=True
        )

    eicar = safe + b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
    with pytest.raises(AppError, match="malware_detected"):
        process_product_file(
            _write(tmp_path, "eicar.png", eicar), "eicar.png", hosted_environment=False
        )


def test_maps_document_extraction_errors_to_safe_upload_error(tmp_path) -> None:
    with pytest.raises(AppError) as exc_info:
        process_product_file(
            _write(tmp_path, "bad.pdf", b"%PDF-invalid"),
            "bad.pdf",
            hosted_environment=False,
        )

    assert exc_info.value.code == "pdf_parse_failed"
    assert "safely processed" in exc_info.value.message
