"""Mapping and safe error handling for cutover activation routes."""

from collections.abc import Callable

from coeus.core.errors import AppError
from coeus.domain.cutover_activation import CutoverManifest, CutoverReleaseState
from coeus.schemas.cutover_activation import (
    CutoverManifestPayload,
    CutoverManifestResponse,
    CutoverReleaseStateResponse,
    CutoverSliceApprovalResponse,
    CutoverSliceStateResponse,
)
from coeus.services.cutover_activation import (
    CutoverActivationConflict,
    CutoverActivationDenied,
)


def manifest(payload: CutoverManifestPayload) -> CutoverManifest:
    return CutoverManifest(**payload.model_dump())


def release_state(state: CutoverReleaseState) -> CutoverReleaseStateResponse:
    return CutoverReleaseStateResponse(
        candidate_hash=state.candidate_hash,
        manifest=CutoverManifestResponse(**vars(state.manifest)) if state.manifest else None,
        slices=[
            CutoverSliceStateResponse(
                **{key: value for key, value in vars(item).items() if key != "approvals"},
                approvals=[CutoverSliceApprovalResponse(**vars(row)) for row in item.approvals],
            )
            for item in state.slices
        ],
        eligible=state.eligible,
    )


def call_cutover[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except CutoverActivationDenied as exc:
        raise AppError(403, "cutover_activation_denied", str(exc)) from exc
    except CutoverActivationConflict as exc:
        raise AppError(409, "cutover_activation_conflict", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "cutover_activation_invalid", str(exc)) from exc
