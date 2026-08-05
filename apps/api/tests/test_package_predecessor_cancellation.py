"""Domain and HTTP-contract tests for explicit predecessor cancellation."""

from dataclasses import replace
from uuid import uuid4

import pytest

from coeus.api.package_predecessor_cancellation_contracts import call_cancellation
from coeus.core.errors import AppError
from coeus.domain.package_predecessor_cancellation import (
    CancelPredecessorCommand,
    DependantDisposition,
    DependantDispositionAction,
    PredecessorCancellationConflict,
    PredecessorCancellationDenied,
    PredecessorCancellationRequest,
    cancellation_hash,
)


def _request() -> PredecessorCancellationRequest:
    return PredecessorCancellationRequest(
        uuid4(),
        uuid4(),
        1,
        2,
        uuid4(),
        3,
        (DependantDisposition(uuid4(), 4, DependantDispositionAction.UNLINK),),
    )


def test_cancellation_hash_is_order_independent_and_actor_bound() -> None:
    request = _request()
    second = DependantDisposition(uuid4(), 1, DependantDispositionAction.CANCEL)
    request = replace(request, dispositions=(*request.dispositions, second))
    actor = uuid4()
    reversed_request = replace(request, dispositions=tuple(reversed(request.dispositions)))
    assert cancellation_hash(actor, request) == cancellation_hash(actor, reversed_request)
    assert cancellation_hash(uuid4(), request) != cancellation_hash(actor, request)


@pytest.mark.parametrize(
    ("action", "replacement", "replacement_version"),
    [
        (DependantDispositionAction.REPLACE, None, None),
        (DependantDispositionAction.UNLINK, uuid4(), 1),
        (DependantDispositionAction.REPLACE, uuid4(), None),
    ],
)
def test_disposition_rejects_incomplete_or_inappropriate_replacement(
    action: DependantDispositionAction,
    replacement: object,
    replacement_version: int | None,
) -> None:
    with pytest.raises(ValueError):
        DependantDisposition(
            uuid4(),
            1,
            action,
            replacement,
            replacement_version,  # type: ignore[arg-type]
        )


def test_request_rejects_duplicate_dependants_and_invalid_versions() -> None:
    request = _request()
    with pytest.raises(ValueError):
        replace(request, dispositions=request.dispositions * 2)
    with pytest.raises(ValueError):
        replace(request, expected_package_version=0)


def test_command_rejects_invalid_identity_evidence() -> None:
    request = _request()
    with pytest.raises(ValueError):
        CancelPredecessorCommand(uuid4(), "", uuid4(), request, "f" * 64)
    with pytest.raises(ValueError):
        CancelPredecessorCommand(uuid4(), "key", uuid4(), request, "short")


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (PredecessorCancellationDenied("hidden"), 404, "work_package_not_found"),
        (
            PredecessorCancellationConflict("changed"),
            409,
            "predecessor_cancellation_conflict",
        ),
        (ValueError("invalid"), 422, "predecessor_cancellation_invalid"),
    ],
)
def test_contract_maps_failures_without_leaking_denial_detail(
    error: Exception, status: int, code: str
) -> None:
    def fail() -> None:
        raise error

    with pytest.raises(AppError) as captured:
        call_cancellation(fail)
    assert captured.value.status_code == status
    assert captured.value.code == code
