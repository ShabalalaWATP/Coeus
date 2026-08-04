"""Safe HTTP mapping for legacy-calendar import contracts."""

from collections.abc import Callable

from coeus.core.errors import AppError
from coeus.domain.calendar_import import (
    CalendarImportConflict,
    CalendarImportPreview,
    CalendarImportResult,
)
from coeus.schemas.calendar_import import (
    CalendarImportFindingResponse,
    CalendarImportPreviewResponse,
    CalendarImportResultResponse,
)


def preview_response(preview: CalendarImportPreview) -> CalendarImportPreviewResponse:
    return CalendarImportPreviewResponse(
        preview_hash=preview.preview_hash,
        source_digest=preview.source_digest,
        state_digest=preview.state_digest,
        source_count=preview.source_count,
        importable_count=preview.importable_count,
        existing_count=preview.existing_count,
        findings=[CalendarImportFindingResponse(**vars(item)) for item in preview.findings],
    )


def result_response(result: CalendarImportResult) -> CalendarImportResultResponse:
    return CalendarImportResultResponse(**vars(result))


def call_calendar_import[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except CalendarImportConflict as exc:
        raise AppError(409, "calendar_import_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "calendar_import_invalid", str(exc)) from exc
