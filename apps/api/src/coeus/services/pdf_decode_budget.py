"""Hard decoded-work limits for untrusted PDF content and Form streams."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from pypdf import filters
from pypdf.errors import LimitReachedError
from pypdf.generic import (
    ArrayObject,
    ContentStream,
    DecodedStreamObject,
    DictionaryObject,
    IndirectObject,
    StreamObject,
)

MAX_PDF_DECODED_STREAM_BYTES = 1_000_000
MAX_PDF_DECODED_DOCUMENT_BYTES = 8_000_000
MAX_PDF_CONTENT_STREAMS = 2_048
MAX_PDF_FORM_INVOCATIONS = 2_048
MAX_PDF_CONTENT_OPERATIONS = 100_000
MAX_PDF_FORM_DEPTH = 32

_PER_STREAM_FILTER_LIMITS = (
    "JBIG2_MAX_OUTPUT_LENGTH",
    "LZW_MAX_OUTPUT_LENGTH",
    "RUN_LENGTH_MAX_OUTPUT_LENGTH",
    "ZLIB_MAX_OUTPUT_LENGTH",
)
_Identity = tuple[object, ...]


class PdfDecodedStreamLimitError(ValueError):
    """PDF decoded content exceeded a fixed parser-work budget."""


@dataclass(frozen=True)
class _ContentInvocation:
    obj: DictionaryObject
    content_key: str | None
    form_depth: int
    active_forms: frozenset[_Identity]


def validate_pdf_decoded_streams(pages: Iterable[DictionaryObject]) -> None:
    """Model and bound the page/Form work performed by text extraction."""
    budget = _PdfStreamBudget()
    for page in pages:
        budget.add_page(page)
    budget.validate()


class _PdfStreamBudget:
    def __init__(self) -> None:
        self.pending: list[_ContentInvocation] = []
        self.decoded_total = 0
        self.stream_count = 0
        self.form_invocations = 0
        self.operation_count = 0

    def add_page(self, page: DictionaryObject) -> None:
        self.pending.append(_ContentInvocation(page, "/Contents", 0, frozenset()))

    def validate(self) -> None:
        while self.pending:
            self._consume(self.pending.pop())

    def _consume(self, invocation: _ContentInvocation) -> None:
        resources = _inherited_resources(invocation.obj)
        content_value: object | None = (
            invocation.obj
            if invocation.content_key is None
            else _raw_optional(invocation.obj, invocation.content_key)
        )
        if content_value is None:
            return
        data = self._decode_content(content_value)
        operations = _parse_operations(data)
        self.operation_count += len(operations)
        if self.operation_count > MAX_PDF_CONTENT_OPERATIONS:
            raise PdfDecodedStreamLimitError("PDF content contains too many operations")
        if resources is None or not resources:
            return
        self._queue_forms(invocation, resources, operations)

    def _queue_forms(
        self,
        invocation: _ContentInvocation,
        resources: DictionaryObject,
        operations: list[tuple[list[object], bytes]],
    ) -> None:
        xobjects = _resolve(_raw_optional(resources, "/XObject"))
        if not isinstance(xobjects, DictionaryObject):
            return
        for operands, operator in operations:
            if operator != b"Do" or not operands:
                continue
            candidate = _raw_optional(xobjects, operands[0])
            resolved_candidate = _resolve(candidate)
            if not isinstance(resolved_candidate, StreamObject):
                continue
            if resolved_candidate.get("/Subtype") == "/Image":
                continue
            identity = _identity(candidate, resolved_candidate)
            if identity in invocation.active_forms:
                continue
            depth = invocation.form_depth + 1
            if depth > MAX_PDF_FORM_DEPTH:
                raise PdfDecodedStreamLimitError("PDF Form nesting is too deep")
            self.form_invocations += 1
            if self.form_invocations > MAX_PDF_FORM_INVOCATIONS:
                raise PdfDecodedStreamLimitError("PDF invokes too many Form objects")
            self.pending.append(
                _ContentInvocation(
                    resolved_candidate,
                    None,
                    depth,
                    invocation.active_forms | {identity},
                )
            )

    def _decode_content(self, value: object) -> bytes:
        resolved = _resolve(value)
        if isinstance(resolved, ArrayObject):
            return self._decode_array(value, resolved)
        if isinstance(resolved, StreamObject):
            return self._decode_stream(resolved)
        return b""

    def _decode_array(self, original: object, streams: ArrayObject) -> bytes:
        if len(streams) > MAX_PDF_CONTENT_STREAMS:
            raise PdfDecodedStreamLimitError("PDF contains too many content streams")
        array_identity = _identity(original, streams)
        data = bytearray()
        for item in streams:
            resolved = _resolve(item)
            if isinstance(resolved, ArrayObject):
                detail = "cyclic" if _identity(item, resolved) == array_identity else "nested"
                raise PdfDecodedStreamLimitError(f"PDF contains a {detail} content array")
            if isinstance(resolved, StreamObject):
                data.extend(self._decode_stream(resolved))
            if not data or data[-1:] != b"\n":
                self._charge_decoded(1)
                data.extend(b"\n")
        return bytes(data)

    def _decode_stream(self, stream: StreamObject) -> bytes:
        self.stream_count += 1
        if self.stream_count > MAX_PDF_CONTENT_STREAMS:
            raise PdfDecodedStreamLimitError("PDF contains too many content streams")
        try:
            data = stream.get_data()
        except LimitReachedError as exc:
            raise PdfDecodedStreamLimitError("PDF content stream is too large") from exc
        if len(data) > MAX_PDF_DECODED_STREAM_BYTES:
            raise PdfDecodedStreamLimitError("PDF content stream is too large")
        self._charge_decoded(len(data))
        return data

    def _charge_decoded(self, size: int) -> None:
        self.decoded_total += size
        if self.decoded_total > MAX_PDF_DECODED_DOCUMENT_BYTES:
            raise PdfDecodedStreamLimitError("PDF decoded content is too large")


def _parse_operations(data: bytes) -> list[tuple[list[object], bytes]]:
    stream = DecodedStreamObject()
    stream.set_data(data)
    try:
        operations = ContentStream(stream, None, "bytes").operations
        return cast(list[tuple[list[object], bytes]], operations)
    except (LimitReachedError, RecursionError) as exc:
        raise PdfDecodedStreamLimitError("PDF content operations are too complex") from exc


def _inherited_resources(value: DictionaryObject) -> DictionaryObject | None:
    try:
        resources = value.get_inherited("/Resources", default=DictionaryObject())
    except LimitReachedError as exc:
        raise PdfDecodedStreamLimitError("PDF resource inheritance is cyclic") from exc
    return resources if isinstance(resources, DictionaryObject) else None


def _raw_optional(value: DictionaryObject, key: object) -> object | None:
    try:
        return cast(object, value.raw_get(key))
    except KeyError:
        return None


def _resolve(value: object | None) -> object | None:
    return value.get_object() if isinstance(value, IndirectObject) else value


def _identity(original: object | None, resolved: object) -> _Identity:
    if isinstance(original, IndirectObject):
        return ("indirect", id(original.pdf), original.idnum, original.generation)
    return ("direct", id(resolved))


def _lower_pypdf_decoder_limits() -> None:
    for name in _PER_STREAM_FILTER_LIMITS:
        setattr(filters, name, min(getattr(filters, name), MAX_PDF_DECODED_STREAM_BYTES))
    filters.MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH = min(
        filters.MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH,
        MAX_PDF_DECODED_DOCUMENT_BYTES,
    )


_lower_pypdf_decoder_limits()
