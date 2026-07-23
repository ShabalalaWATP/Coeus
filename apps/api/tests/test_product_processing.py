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


@pytest.mark.parametrize(
    "relationship",
    [
        b"<Relationship TargetMode='External'/>",
        b'<Relationship Id="rId1" TargetMode = "External"/>',
        (
            b"<pr:Relationship xmlns:pr='http://schemas.openxmlformats.org/package/2006/"
            b"relationships' Target='https://example.invalid' TargetMode = 'External'/>"
        ),
    ],
)
@pytest.mark.parametrize(
    ("filename", "document_part", "relationship_part"),
    [
        ("linked.docx", "word/document.xml", "word/_rels/document.xml.rels"),
        ("linked.pptx", "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"),
    ],
)
def test_rejects_semantic_external_office_relationship_variants(
    tmp_path,
    relationship: bytes,
    filename: str,
    document_part: str,
    relationship_part: str,
) -> None:
    relationships = (
        b"<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
        + relationship
        + b"</Relationships>"
    )
    content = _zip(
        **{
            document_part: b"<document />",
            relationship_part: relationships,
        }
    )

    with pytest.raises(AppError, match="office_external_content_rejected"):
        process_product_file(
            _write(tmp_path, filename, content),
            filename,
            hosted_environment=False,
        )


@pytest.mark.parametrize(
    "relationships",
    [
        b"<Relationships><Relationship></Relationships>",
        (
            b"<!DOCTYPE Relationships [<!ENTITY target 'External'>]>"
            b"<Relationships><Relationship TargetMode='&target;'/></Relationships>"
        ),
    ],
)
def test_rejects_malformed_or_unsafe_relationship_xml(tmp_path, relationships: bytes) -> None:
    content = _zip(
        **{
            "word/document.xml": b"<document />",
            "word/_rels/document.xml.rels": relationships,
        }
    )

    with pytest.raises(AppError, match="office_relationships_invalid"):
        process_product_file(
            _write(tmp_path, "relationships.docx", content),
            "relationships.docx",
            hosted_environment=False,
        )


def test_accepts_internal_pptx_relationships(tmp_path) -> None:
    content = _zip(
        **{
            "ppt/presentation.xml": b"<p:presentation xmlns:p='urn:p' />",
            "ppt/slides/slide1.xml": (
                b"<p:sld xmlns:p='urn:p' xmlns:a='urn:a'><a:t>Synthetic slide</a:t></p:sld>"
            ),
            "ppt/slides/_rels/slide1.xml.rels": (
                b"<Relationships><Relationship Target='../media/image1.png' "
                b"TargetMode='Internal'/></Relationships>"
            ),
        }
    )

    processed = process_product_file(
        _write(tmp_path, "internal.pptx", content),
        "internal.pptx",
        hosted_environment=False,
    )

    assert processed.detected_mime_type == product_processing.PPTX_MIME
    assert "Synthetic slide" in processed.extracted_text


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


def test_rejects_excessive_central_directory_before_zipfile_construction(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = _zip(
        **{
            "word/document.xml": b"<document />",
            "word/styles.xml": b"<styles />",
        }
    )
    monkeypatch.setattr(product_processing, "MAX_OFFICE_ZIP_MEMBERS", 1)

    def unexpected_zipfile(*_args, **_kwargs):
        raise AssertionError("ZipFile must not parse an over-budget central directory")

    monkeypatch.setattr(product_processing, "ZipFile", unexpected_zipfile)

    with pytest.raises(AppError, match="office_archive_too_large"):
        process_product_file(
            _write(tmp_path, "many.docx", content),
            "many.docx",
            hosted_environment=False,
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
