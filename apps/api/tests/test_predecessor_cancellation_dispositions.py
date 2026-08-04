"""Dependant disposition rules for cancelling a predecessor work package."""

from uuid import UUID, uuid4

import pytest

from coeus.domain.package_predecessor_cancellation import (
    DependantDisposition,
    DependantDispositionAction,
    PredecessorCancellationConflict,
    PredecessorCancellationRequest,
    cancellation_hash,
)
from coeus.persistence.package_predecessor_cancellation_postgres import (
    _preview,
    _validate_dispositions,
)

UNIT = uuid4()
PREDECESSOR, FIRST, SECOND, SPARE = uuid4(), uuid4(), uuid4(), uuid4()


def _request(
    *dispositions: DependantDisposition, **overrides: object
) -> PredecessorCancellationRequest:
    values: dict[str, object] = {
        "unit_id": UNIT,
        "package_id": PREDECESSOR,
        "expected_package_version": 1,
        "expected_ownership_version": 1,
        "authorising_grant_id": uuid4(),
        "expected_grant_version": 1,
        "dispositions": dispositions,
    }
    values.update(overrides)
    return PredecessorCancellationRequest(**values)  # type: ignore[arg-type]


def _node(package_id: UUID, *predecessors: UUID, version: int = 1) -> dict[str, object]:
    return {"package_id": package_id, "version": version, "predecessors": list(predecessors)}


def _package(version: int = 1) -> dict[str, object]:
    return {"package_id": PREDECESSOR, "version": version}


def test_unlinking_the_only_dependant_leaves_a_valid_graph() -> None:
    request = _request(DependantDisposition(FIRST, 1, DependantDispositionAction.UNLINK))
    rows = (_node(PREDECESSOR), _node(FIRST, PREDECESSOR))

    _validate_dispositions(request, _package(), rows)  # type: ignore[arg-type]


def test_every_direct_dependant_needs_exactly_one_disposition() -> None:
    rows = (_node(PREDECESSOR), _node(FIRST, PREDECESSOR), _node(SECOND, PREDECESSOR))

    with pytest.raises(PredecessorCancellationConflict, match="exactly one disposition"):
        _validate_dispositions(
            _request(DependantDisposition(FIRST, 1, DependantDispositionAction.UNLINK)),
            _package(),  # type: ignore[arg-type]
            rows,  # type: ignore[arg-type]
        )
    with pytest.raises(PredecessorCancellationConflict, match="exactly one disposition"):
        _validate_dispositions(
            _request(
                DependantDisposition(FIRST, 1, DependantDispositionAction.UNLINK),
                DependantDisposition(SPARE, 1, DependantDispositionAction.UNLINK),
            ),
            _package(),  # type: ignore[arg-type]
            (_node(PREDECESSOR), _node(FIRST, PREDECESSOR), _node(SPARE)),  # type: ignore[arg-type]
        )


def test_a_stale_dependant_version_is_refused() -> None:
    rows = (_node(PREDECESSOR), _node(FIRST, PREDECESSOR, version=4))

    with pytest.raises(PredecessorCancellationConflict, match="dependant package evidence changed"):
        _validate_dispositions(
            _request(DependantDisposition(FIRST, 1, DependantDispositionAction.UNLINK)),
            _package(),  # type: ignore[arg-type]
            rows,  # type: ignore[arg-type]
        )


def test_a_cancelled_dependant_cannot_leave_downstream_work_orphaned() -> None:
    # SECOND depends on FIRST, so cancelling FIRST without a disposition for
    # SECOND would strand it.
    rows = (_node(PREDECESSOR), _node(FIRST, PREDECESSOR), _node(SECOND, FIRST))

    with pytest.raises(PredecessorCancellationConflict, match="unresolved downstream dependants"):
        _validate_dispositions(
            _request(DependantDisposition(FIRST, 1, DependantDispositionAction.CANCEL)),
            _package(),  # type: ignore[arg-type]
            rows,  # type: ignore[arg-type]
        )


def test_a_cancelled_leaf_dependant_is_accepted() -> None:
    rows = (_node(PREDECESSOR), _node(FIRST, PREDECESSOR))

    _validate_dispositions(
        _request(DependantDisposition(FIRST, 1, DependantDispositionAction.CANCEL)),
        _package(),  # type: ignore[arg-type]
        rows,  # type: ignore[arg-type]
    )


def test_a_replacement_must_exist_at_the_expected_version_and_differ_from_the_predecessor() -> None:
    rows = (_node(PREDECESSOR), _node(FIRST, PREDECESSOR), _node(SPARE, version=2))

    _validate_dispositions(
        _request(DependantDisposition(FIRST, 1, DependantDispositionAction.REPLACE, SPARE, 2)),
        _package(),  # type: ignore[arg-type]
        rows,  # type: ignore[arg-type]
    )
    for replacement, version in ((uuid4(), 2), (SPARE, 9), (PREDECESSOR, 1)):
        with pytest.raises(
            PredecessorCancellationConflict, match="replacement package evidence changed"
        ):
            _validate_dispositions(
                _request(
                    DependantDisposition(
                        FIRST, 1, DependantDispositionAction.REPLACE, replacement, version
                    )
                ),
                _package(),  # type: ignore[arg-type]
                rows,  # type: ignore[arg-type]
            )


def test_a_replacement_that_creates_a_cycle_is_refused() -> None:
    rows = (_node(PREDECESSOR), _node(FIRST, PREDECESSOR), _node(SECOND, FIRST))

    with pytest.raises(ValueError):
        _validate_dispositions(
            _request(
                DependantDisposition(FIRST, 1, DependantDispositionAction.REPLACE, SECOND, 1),
                DependantDisposition(SECOND, 1, DependantDispositionAction.UNLINK),
            ),
            _package(),  # type: ignore[arg-type]
            rows,  # type: ignore[arg-type]
        )


def test_a_preview_reports_the_planned_version_and_a_stable_hash() -> None:
    actor = uuid4()
    request = _request(DependantDisposition(FIRST, 1, DependantDispositionAction.UNLINK))

    preview = _preview(actor, request, _package(version=3))  # type: ignore[arg-type]

    assert preview.package_version == 3
    assert preview.planned_package_version == 4
    assert preview.dependant_count == 1
    assert preview.preview_hash == cancellation_hash(actor, request)
    assert preview.preview_hash != cancellation_hash(uuid4(), request)


def test_a_disposition_pairs_its_replacement_identity_with_a_version() -> None:
    with pytest.raises(ValueError, match="dependant package version must be positive"):
        DependantDisposition(FIRST, 0, DependantDispositionAction.UNLINK)
    with pytest.raises(ValueError, match="supplied together"):
        DependantDisposition(FIRST, 1, DependantDispositionAction.REPLACE, SPARE)
    with pytest.raises(ValueError, match="only replacement disposition"):
        DependantDisposition(FIRST, 1, DependantDispositionAction.UNLINK, SPARE, 1)
    with pytest.raises(ValueError, match="replacement package version must be positive"):
        DependantDisposition(FIRST, 1, DependantDispositionAction.REPLACE, SPARE, 0)


def test_a_request_bounds_its_versions_and_dependant_identities() -> None:
    unlink = DependantDisposition(FIRST, 1, DependantDispositionAction.UNLINK)
    with pytest.raises(ValueError, match="evidence versions must be positive"):
        _request(unlink, expected_ownership_version=0)
    with pytest.raises(ValueError, match="unique and bounded"):
        _request(unlink, unlink)
