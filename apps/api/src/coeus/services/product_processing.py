"""Bounded verification and extraction for analyst-submitted product files."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePath
from zipfile import BadZipFile, ZipFile, ZipInfo

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError

from coeus.core.errors import AppError
from coeus.services.document_extraction import (
    PPTX_MIME,
    DocumentExtractionError,
    extract_pages,
)
from coeus.services.office_archive import (
    OfficeArchiveInvalidError,
    OfficeArchiveLimitError,
    preflight_office_archive,
    read_bounded_member,
    validate_office_archive,
)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"
PNG_MIME = "image/png"
JPEG_MIME = "image/jpeg"
WEBP_MIME = "image/webp"
ALLOWED_SUFFIXES = {
    PDF_MIME: frozenset({".pdf"}),
    DOCX_MIME: frozenset({".docx"}),
    PPTX_MIME: frozenset({".pptx"}),
    PNG_MIME: frozenset({".png"}),
    JPEG_MIME: frozenset({".jpg", ".jpeg"}),
    WEBP_MIME: frozenset({".webp"}),
}
MAX_QC_TEXT_CHARACTERS = 100_000
MAX_OFFICE_ZIP_MEMBERS = 5_000
MAX_OFFICE_EXPANDED_BYTES = 50_000_000
MAX_OFFICE_CENTRAL_DIRECTORY_BYTES = 50_000_000
MAX_RELATIONSHIP_BYTES = 1_000_000


@dataclass(frozen=True)
class ProcessedProductFile:
    detected_mime_type: str
    asset_type: str
    preview_kind: str
    extracted_text: str


def process_product_file(
    path: Path,
    filename: str,
    *,
    hosted_environment: bool,
) -> ProcessedProductFile:
    content = path.read_bytes()
    detected = _detect_type(content)
    suffix = PurePath(filename).suffix.casefold()
    if suffix not in ALLOWED_SUFFIXES.get(detected, frozenset()):
        raise AppError(422, "asset_type_mismatch", "File extension does not match its content.")
    _malware_check(content, hosted_environment)
    if detected.startswith("image/"):
        return ProcessedProductFile(detected, suffix.removeprefix("."), "image", "")
    try:
        pages = extract_pages(content, detected)
    except DocumentExtractionError as exc:
        raise AppError(
            422, exc.code, "The uploaded product could not be safely processed."
        ) from exc
    extracted = "\n\n".join(f"Page or slide {page.page_number}\n{page.text}" for page in pages)
    if not extracted.strip():
        raise AppError(422, "document_text_missing", "The product contains no extractable text.")
    return ProcessedProductFile(
        detected,
        suffix.removeprefix("."),
        "pdf" if detected == PDF_MIME else "text",
        extracted[:MAX_QC_TEXT_CHARACTERS],
    )


def _detect_type(content: bytes) -> str:
    if content.startswith(b"%PDF-"):
        return PDF_MIME
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG_MIME
    if content.startswith(b"\xff\xd8\xff"):
        return JPEG_MIME
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return WEBP_MIME
    if content.startswith(b"PK"):
        return _office_type(content)
    raise AppError(422, "asset_type_unsupported", "Use PDF, DOCX, PPTX, PNG, JPEG or WebP.")


def _office_type(content: bytes) -> str:
    try:
        preflight_office_archive(
            content,
            max_members=MAX_OFFICE_ZIP_MEMBERS,
            max_directory_bytes=MAX_OFFICE_CENTRAL_DIRECTORY_BYTES,
        )
        with ZipFile(BytesIO(content)) as archive:
            members = validate_office_archive(
                archive,
                max_members=MAX_OFFICE_ZIP_MEMBERS,
                max_expanded_bytes=MAX_OFFICE_EXPANDED_BYTES,
            )
            names = {member.filename.casefold() for member in members}
            if any(name.endswith("vbaproject.bin") for name in names):
                raise AppError(422, "office_macros_rejected", "Macro-enabled products are blocked.")
            _reject_external_relationships(archive, members)
    except AppError:
        raise
    except OfficeArchiveLimitError as exc:
        raise AppError(
            422,
            "office_archive_too_large",
            "Office product exceeds safe processing limits.",
        ) from exc
    except OfficeArchiveInvalidError as exc:
        raise AppError(422, "office_archive_invalid", "Office product is malformed.") from exc
    except BadZipFile as exc:
        raise AppError(422, "office_archive_invalid", "Office product is malformed.") from exc
    if "word/document.xml" in names:
        return DOCX_MIME
    if "ppt/presentation.xml" in names:
        return PPTX_MIME
    raise AppError(422, "asset_type_unsupported", "Office product type is not supported.")


def _reject_external_relationships(archive: ZipFile, members: tuple[ZipInfo, ...]) -> None:
    for member in members:
        if not member.filename.casefold().endswith(".rels"):
            continue
        content = read_bounded_member(archive, member, MAX_RELATIONSHIP_BYTES)
        try:
            root = ElementTree.fromstring(content, forbid_dtd=True)
        except (DefusedXmlException, ParseError) as exc:
            raise AppError(
                422,
                "office_relationships_invalid",
                "Office relationship metadata is malformed.",
            ) from exc
        if any(node.attrib.get("TargetMode") == "External" for node in root.iter()):
            raise AppError(
                422,
                "office_external_content_rejected",
                "Office products with external content are blocked.",
            )


def _malware_check(content: bytes, hosted_environment: bool) -> None:
    if hosted_environment:
        raise AppError(
            503,
            "malware_scanner_unavailable",
            "Product upload is unavailable until the malware scanner is configured.",
        )
    signature = b"EICAR-STANDARD-" + b"ANTIVIRUS-TEST-FILE"
    if signature in content:
        raise AppError(422, "malware_detected", "The uploaded product failed malware screening.")
