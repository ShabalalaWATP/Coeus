"""HTTP mapping for synthetic fixture domain responses and failures."""

from collections.abc import Callable

from coeus.core.errors import AppError
from coeus.domain.synthetic_organisation_fixture import (
    SyntheticFixtureConflict,
    SyntheticFixtureCounts,
    SyntheticFixtureIdempotencyConflict,
    SyntheticFixturePreview,
    SyntheticFixtureResult,
    SyntheticFixtureUnavailable,
)
from coeus.schemas.synthetic_organisation_fixture import (
    SyntheticFixtureCountsResponse,
    SyntheticFixtureFindingResponse,
    SyntheticFixturePreviewResponse,
    SyntheticFixtureResultResponse,
)


def call_fixture[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except SyntheticFixtureUnavailable as exc:
        raise AppError(403, "synthetic_fixture_unavailable", str(exc)) from exc
    except SyntheticFixtureIdempotencyConflict as exc:
        raise AppError(409, "synthetic_fixture_idempotency_conflict", str(exc)) from exc
    except SyntheticFixtureConflict as exc:
        raise AppError(409, "synthetic_fixture_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "synthetic_fixture_invalid", str(exc)) from exc


def preview_response(preview: SyntheticFixturePreview) -> SyntheticFixturePreviewResponse:
    return SyntheticFixturePreviewResponse(
        manifest_version=preview.manifest_version,
        preview_hash=preview.preview_hash,
        can_apply=preview.can_apply,
        creates=_counts(preview.creates),
        unchanged=_counts(preview.unchanged),
        findings=[SyntheticFixtureFindingResponse(**vars(item)) for item in preview.findings],
    )


def result_response(result: SyntheticFixtureResult) -> SyntheticFixtureResultResponse:
    return SyntheticFixtureResultResponse(
        command_id=result.command_id,
        manifest_version=result.manifest_version,
        created=_counts(result.created),
        replayed=result.replayed,
        reconciled_rows=result.reconciled_rows,
    )


def _counts(counts: SyntheticFixtureCounts) -> SyntheticFixtureCountsResponse:
    return SyntheticFixtureCountsResponse(**vars(counts), total=counts.total)
