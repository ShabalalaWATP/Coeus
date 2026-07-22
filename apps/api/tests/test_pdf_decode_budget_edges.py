import pytest
from pypdf.errors import LimitReachedError
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject

from coeus.services import pdf_decode_budget


def test_pdf_budget_handles_empty_and_non_stream_content() -> None:
    budget = pdf_decode_budget._PdfStreamBudget()
    budget.add_page(DictionaryObject())
    page_without_content = DictionaryObject(
        {NameObject("/Resources"): DictionaryObject({NameObject("/Marker"): NameObject("/Yes")})}
    )
    budget.add_page(page_without_content)
    budget.validate()

    assert budget._decode_content(NameObject("/NotAStream")) == b""


def test_pdf_budget_bounds_arrays_and_raw_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    first = DecodedStreamObject()
    first.set_data(b"first")
    second = DecodedStreamObject()
    second.set_data(b"second\n")
    budget = pdf_decode_budget._PdfStreamBudget()

    assert budget._decode_content(ArrayObject([first, second])) == b"first\nsecond\n"
    with pytest.raises(pdf_decode_budget.PdfDecodedStreamLimitError, match="nested"):
        budget._decode_content(ArrayObject([ArrayObject()]))

    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_CONTENT_STREAMS", 0)
    with pytest.raises(pdf_decode_budget.PdfDecodedStreamLimitError, match="too many"):
        budget._decode_content(ArrayObject([first]))
    with pytest.raises(pdf_decode_budget.PdfDecodedStreamLimitError, match="too many"):
        budget._decode_content(first)

    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_CONTENT_STREAMS", 2_048)
    monkeypatch.setattr(pdf_decode_budget, "MAX_PDF_DECODED_STREAM_BYTES", 0)
    with pytest.raises(pdf_decode_budget.PdfDecodedStreamLimitError, match="too large"):
        pdf_decode_budget._PdfStreamBudget()._decode_content(first)


def test_pdf_budget_handles_xobject_edge_cases() -> None:
    invalid = NameObject("/NotAStream")
    image = DecodedStreamObject()
    image[NameObject("/Subtype")] = NameObject("/Image")
    cycle = DecodedStreamObject()
    nested = DecodedStreamObject()
    xobjects = DictionaryObject(
        {
            NameObject("/Invalid"): invalid,
            NameObject("/Image"): image,
            NameObject("/Cycle"): cycle,
            NameObject("/Nested"): nested,
        }
    )
    resources = DictionaryObject({NameObject("/XObject"): xobjects})
    cycle_identity = pdf_decode_budget._identity(cycle, cycle)
    invocation = pdf_decode_budget._ContentInvocation(
        DictionaryObject(),
        None,
        pdf_decode_budget.MAX_PDF_FORM_DEPTH,
        frozenset({cycle_identity}),
    )
    operations = [
        ([], b"Do"),
        ([NameObject("/Invalid")], b"Do"),
        ([NameObject("/Image")], b"Do"),
        ([NameObject("/Cycle")], b"Do"),
    ]
    budget = pdf_decode_budget._PdfStreamBudget()
    budget._queue_forms(invocation, resources, operations)

    with pytest.raises(pdf_decode_budget.PdfDecodedStreamLimitError, match="nesting"):
        budget._queue_forms(
            invocation,
            resources,
            [([NameObject("/Nested")], b"Do")],
        )


def test_pdf_budget_maps_decoder_parser_and_resource_cycles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = DecodedStreamObject()
    stream.set_data(b"bounded")

    def limit_reached(_self: object) -> bytes:
        raise LimitReachedError("synthetic decoder limit")

    monkeypatch.setattr(DecodedStreamObject, "get_data", limit_reached)
    with pytest.raises(pdf_decode_budget.PdfDecodedStreamLimitError, match="too large"):
        pdf_decode_budget._PdfStreamBudget()._decode_content(stream)

    class RecursiveContentStream:
        def __init__(self, *_args: object) -> None:
            raise RecursionError

    monkeypatch.setattr(pdf_decode_budget, "ContentStream", RecursiveContentStream)
    with pytest.raises(pdf_decode_budget.PdfDecodedStreamLimitError, match="too complex"):
        pdf_decode_budget._parse_operations(b"q Q")

    cyclic = DictionaryObject()
    cyclic[NameObject("/Parent")] = cyclic
    with pytest.raises(pdf_decode_budget.PdfDecodedStreamLimitError, match="inheritance"):
        pdf_decode_budget._inherited_resources(cyclic)

    assert pdf_decode_budget._identity(None, stream)[0] == "direct"
