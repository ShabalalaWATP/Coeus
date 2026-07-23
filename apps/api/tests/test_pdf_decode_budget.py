import zlib
from io import BytesIO

import pytest
from pypdf import PageObject, PdfReader, PdfWriter, filters
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    EncodedStreamObject,
    NameObject,
)
from reportlab.pdfgen.canvas import Canvas

from coeus.services import pdf_decode_budget
from coeus.services.document_extraction import DocumentExtractionError, extract_pages


def test_pdf_decoder_uses_the_application_stream_limit() -> None:
    assert filters.ZLIB_MAX_OUTPUT_LENGTH == pdf_decode_budget.MAX_PDF_DECODED_STREAM_BYTES
    assert filters.LZW_MAX_OUTPUT_LENGTH == pdf_decode_budget.MAX_PDF_DECODED_STREAM_BYTES
    assert filters.RUN_LENGTH_MAX_OUTPUT_LENGTH == pdf_decode_budget.MAX_PDF_DECODED_STREAM_BYTES


def test_pdf_accepts_the_exact_stream_limit_and_rejects_one_byte_more(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exact = _pdf_with_page_stream_targets([pdf_decode_budget.MAX_PDF_DECODED_STREAM_BYTES])
    pages = extract_pages(exact, "application/pdf")

    assert len(pages) == 1
    assert "synthetic" in pages[0].text

    def unexpected_extract(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("over-budget content must be rejected before extract_text")

    monkeypatch.setattr(PageObject, "extract_text", unexpected_extract)
    excessive = _pdf_with_page_stream_targets([pdf_decode_budget.MAX_PDF_DECODED_STREAM_BYTES + 1])

    with pytest.raises(DocumentExtractionError, match="pdf_processing_limit_exceeded"):
        extract_pages(excessive, "application/pdf")


def test_pdf_aggregate_budget_accepts_exactly_and_rejects_the_next_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_DECODED_DOCUMENT_BYTES", 1_200)
    exact = _pdf_with_page_stream_targets([400, 400, 400])

    assert len(extract_pages(exact, "application/pdf")) == 3

    excessive = _pdf_with_page_stream_targets([400, 400, 401])
    with pytest.raises(DocumentExtractionError, match="pdf_processing_limit_exceeded"):
        extract_pages(excessive, "application/pdf")


def test_pdf_aggregate_budget_includes_form_xobjects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content, decoded_total = _pdf_with_form_stream_target(500)
    monkeypatch.setattr(
        pdf_decode_budget,
        "MAX_PDF_DECODED_DOCUMENT_BYTES",
        decoded_total,
    )

    pages = extract_pages(content, "application/pdf")
    assert "synthetic form" in pages[0].text

    monkeypatch.setattr(
        pdf_decode_budget,
        "MAX_PDF_DECODED_DOCUMENT_BYTES",
        decoded_total - 1,
    )
    with pytest.raises(DocumentExtractionError, match="pdf_processing_limit_exceeded"):
        extract_pages(content, "application/pdf")


def test_pdf_budget_charges_each_repeated_form_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content, decoded_total = _pdf_with_form_stream_target(500, invocations=2)
    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_DECODED_DOCUMENT_BYTES", decoded_total)
    assert "synthetic form" in extract_pages(content, "application/pdf")[0].text

    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_DECODED_DOCUMENT_BYTES", decoded_total - 1)
    with pytest.raises(DocumentExtractionError, match="pdf_processing_limit_exceeded"):
        extract_pages(content, "application/pdf")


def test_pdf_budget_charges_shared_page_stream_per_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content, stream_size = _pdf_with_shared_page_stream(400)
    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_DECODED_DOCUMENT_BYTES", stream_size * 2)
    assert len(extract_pages(content, "application/pdf")) == 2

    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_DECODED_DOCUMENT_BYTES", stream_size * 2 - 1)
    with pytest.raises(DocumentExtractionError, match="pdf_processing_limit_exceeded"):
        extract_pages(content, "application/pdf")


def test_pdf_budget_uses_inherited_page_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    direct, decoded_total = _pdf_with_form_stream_target(500)
    inherited = _move_page_resources_to_parent(direct)
    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_DECODED_DOCUMENT_BYTES", decoded_total)
    assert "synthetic form" in extract_pages(inherited, "application/pdf")[0].text

    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_DECODED_DOCUMENT_BYTES", decoded_total - 1)
    with pytest.raises(DocumentExtractionError, match="pdf_processing_limit_exceeded"):
        extract_pages(inherited, "application/pdf")


def test_pdf_budget_uses_inherited_form_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    direct, decoded_total = _pdf_with_form_stream_target(500)
    inherited = _move_form_resources_to_parent(direct)
    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_DECODED_DOCUMENT_BYTES", decoded_total)
    assert "synthetic form" in extract_pages(inherited, "application/pdf")[0].text

    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_DECODED_DOCUMENT_BYTES", decoded_total - 1)
    with pytest.raises(DocumentExtractionError, match="pdf_processing_limit_exceeded"):
        extract_pages(inherited, "application/pdf")


def test_pdf_rejects_self_referential_indirect_content_array_before_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _pdf_with_cyclic_content_array()

    def unexpected_extract(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("cyclic content must be rejected before extract_text")

    monkeypatch.setattr(PageObject, "extract_text", unexpected_extract)
    with pytest.raises(DocumentExtractionError, match="pdf_processing_limit_exceeded"):
        extract_pages(content, "application/pdf")


def test_pdf_bounds_content_operations_and_form_invocations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = _pdf_with_raw_content(b"q Q")
    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_CONTENT_OPERATIONS", 2)
    extract_pages(operations, "application/pdf")
    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_CONTENT_OPERATIONS", 1)
    with pytest.raises(DocumentExtractionError, match="pdf_processing_limit_exceeded"):
        extract_pages(operations, "application/pdf")

    forms, _ = _pdf_with_form_stream_target(500, invocations=2)
    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_CONTENT_OPERATIONS", 100_000)
    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_FORM_INVOCATIONS", 1)
    with pytest.raises(DocumentExtractionError, match="pdf_processing_limit_exceeded"):
        extract_pages(forms, "application/pdf")


def test_pdf_without_resources_is_still_decoded_and_operation_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = _remove_page_resources(_pdf_with_raw_content(b"q Q"))
    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_DECODED_STREAM_BYTES", 3)
    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_CONTENT_OPERATIONS", 2)
    assert extract_pages(content, "application/pdf") == ()

    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_CONTENT_OPERATIONS", 1)
    with pytest.raises(DocumentExtractionError, match="pdf_processing_limit_exceeded"):
        extract_pages(content, "application/pdf")

    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_CONTENT_OPERATIONS", 100_000)
    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_DECODED_STREAM_BYTES", 2)
    with pytest.raises(DocumentExtractionError, match="pdf_processing_limit_exceeded"):
        extract_pages(content, "application/pdf")


def _pdf_with_page_stream_targets(targets: list[int]) -> bytes:
    source = BytesIO()
    canvas = Canvas(source)
    for index in range(len(targets)):
        canvas.drawString(72, 720, f"synthetic page {index + 1}")
        canvas.showPage()
    canvas.save()

    reader = PdfReader(BytesIO(source.getvalue()), strict=True)
    originals = [page.get_contents().get_data() for page in reader.pages]
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    for page, original, target in zip(writer.pages, originals, targets, strict=True):
        if target < len(original):
            raise AssertionError("test stream target is smaller than its valid content")
        page[NameObject("/Contents")] = writer._add_object(
            _flate_stream(b" " * (target - len(original)) + original)
        )
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _pdf_with_form_stream_target(target: int, *, invocations: int = 1) -> tuple[bytes, int]:
    source = BytesIO()
    canvas = Canvas(source)
    canvas.beginForm("bounded")
    canvas.drawString(72, 720, "synthetic form")
    canvas.endForm()
    for _ in range(invocations):
        canvas.doForm("bounded")
    canvas.save()

    reader = PdfReader(BytesIO(source.getvalue()), strict=True)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    page = writer.pages[0]
    page_content_size = len(page.get_contents().get_data())
    xobjects = page["/Resources"]["/XObject"]
    form_name, form_reference = next(iter(xobjects.items()))
    form = form_reference.get_object()
    original = form.get_data()
    if target < len(original):
        raise AssertionError("test Form target is smaller than its valid content")
    replacement = _flate_stream(b" " * (target - len(original)) + original)
    for key, value in form.items():
        if key not in {"/Filter", "/Length"}:
            replacement[key] = value
    xobjects[form_name] = writer._add_object(replacement)
    output = BytesIO()
    writer.write(output)
    return output.getvalue(), page_content_size + target * invocations


def _pdf_with_shared_page_stream(target: int) -> tuple[bytes, int]:
    source = BytesIO()
    canvas = Canvas(source)
    canvas.drawString(72, 720, "synthetic shared page")
    canvas.save()
    reader = PdfReader(BytesIO(source.getvalue()), strict=True)
    original = reader.pages[0].get_contents().get_data()
    if target < len(original):
        raise AssertionError("test stream target is smaller than its valid content")
    writer = PdfWriter()
    first = writer.add_page(reader.pages[0])
    second = writer.add_page(reader.pages[0])
    shared = writer._add_object(_flate_stream(b" " * (target - len(original)) + original))
    first[NameObject("/Contents")] = shared
    second[NameObject("/Contents")] = shared
    output = BytesIO()
    writer.write(output)
    return output.getvalue(), target


def _move_page_resources_to_parent(content: bytes) -> bytes:
    reader = PdfReader(BytesIO(content), strict=True)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    page = writer.pages[0]
    resources = page.raw_get("/Resources")
    parent = page.raw_get("/Parent").get_object()
    parent[NameObject("/Resources")] = resources
    del page["/Resources"]
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _remove_page_resources(content: bytes) -> bytes:
    reader = PdfReader(BytesIO(content), strict=True)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    page = writer.pages[0]
    if "/Resources" in page:
        del page["/Resources"]
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _move_form_resources_to_parent(content: bytes) -> bytes:
    reader = PdfReader(BytesIO(content), strict=True)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    xobjects = writer.pages[0]["/Resources"]["/XObject"]
    form = next(iter(xobjects.values())).get_object()
    parent = writer._add_object(
        DictionaryObject({NameObject("/Resources"): form.raw_get("/Resources")})
    )
    form[NameObject("/Parent")] = parent
    del form["/Resources"]
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _pdf_with_cyclic_content_array() -> bytes:
    base = _pdf_with_raw_content(b"q Q")
    reader = PdfReader(BytesIO(base), strict=True)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    streams = ArrayObject()
    reference = writer._add_object(streams)
    streams.append(reference)
    writer.pages[0][NameObject("/Contents")] = reference
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _pdf_with_raw_content(content: bytes) -> bytes:
    source = BytesIO()
    canvas = Canvas(source)
    canvas.drawString(72, 720, "synthetic resources")
    canvas.save()
    reader = PdfReader(BytesIO(source.getvalue()), strict=True)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    stream = EncodedStreamObject()
    stream._data = content
    writer.pages[0][NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _flate_stream(content: bytes) -> EncodedStreamObject:
    stream = EncodedStreamObject()
    stream[NameObject("/Filter")] = NameObject("/FlateDecode")
    stream._data = zlib.compress(content, 9)
    return stream
