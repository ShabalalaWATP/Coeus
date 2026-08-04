"""Disposition matrix for cross-team workflow-leg transfer proposals."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.workflow_leg_transfers import (
    PackageTransferDisposition,
    PackageTransferPlan,
    ProposeWorkflowLegTransfer,
    WorkflowLegTransferConflict,
)
from coeus.persistence.workflow_leg_transfer_validation import (
    _validate_dependency_dispositions,
    _validate_package_inventory,
)

SOURCE, TARGET = uuid4(), uuid4()
START = datetime(2026, 8, 17, 9, tzinfo=UTC)


def _plan(
    package_id: UUID, disposition: PackageTransferDisposition, version: int = 1
) -> PackageTransferPlan:
    if disposition is not PackageTransferDisposition.TRANSFER:
        return PackageTransferPlan(package_id, disposition, version)
    return PackageTransferPlan(
        package_id,
        disposition,
        version,
        uuid4(),
        f"reservation-{package_id}",
        START,
        START + timedelta(hours=2),
        120,
    )


FILLER = uuid4()


def _proposal(*plans: PackageTransferPlan) -> ProposeWorkflowLegTransfer:
    """A proposal needs at least one transferring package, so add a filler."""
    if not any(item.disposition is PackageTransferDisposition.TRANSFER for item in plans):
        plans = (*plans, _plan(FILLER, PackageTransferDisposition.TRANSFER))
    return ProposeWorkflowLegTransfer(
        uuid4(),
        uuid4(),
        WorkflowLeg.RFA,
        SOURCE,
        TARGET,
        uuid4(),
        1,
        1,
        "a" * 64,
        uuid4(),
        1,
        datetime.now(UTC) + timedelta(days=1),
        plans,
        "Synthetic cross-team transfer.",
    )


def _row(
    package_id: UUID,
    state: str,
    version: int = 1,
    remaining: int | None = 120,
    unit_id: UUID | None = None,
) -> dict[str, object]:
    return {
        "package_id": package_id,
        "state": state,
        "version": version,
        "remaining_minutes": remaining,
        "owning_unit_id": SOURCE if unit_id is None else unit_id,
    }


def test_every_workflow_leg_package_needs_a_disposition() -> None:
    planned, unplanned = uuid4(), uuid4()
    proposal = _proposal(_plan(planned, PackageTransferDisposition.TRANSFER))

    with pytest.raises(WorkflowLegTransferConflict, match="needs a disposition"):
        _validate_package_inventory(
            proposal,
            (_row(planned, "in_progress"), _row(unplanned, "ready")),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("version", "unit_id"),
    [(4, None), (1, TARGET)],
)
def test_stale_or_foreign_package_evidence_is_refused(version: int, unit_id: UUID | None) -> None:
    package_id = uuid4()
    proposal = _proposal(_plan(package_id, PackageTransferDisposition.TRANSFER))

    with pytest.raises(WorkflowLegTransferConflict, match="work-package evidence changed"):
        _validate_package_inventory(
            proposal,
            (_row(package_id, "in_progress", version, unit_id=unit_id),),  # type: ignore[arg-type]
        )


def _with_filler(*rows: dict[str, object]) -> tuple[dict[str, object], ...]:
    return (*rows, _row(FILLER, "in_progress"))


@pytest.mark.parametrize("state", ["complete", "cancelled"])
def test_terminal_packages_may_only_be_retained(state: str) -> None:
    package_id = uuid4()
    terminal = _row(package_id, state, remaining=0)

    _validate_package_inventory(
        _proposal(_plan(package_id, PackageTransferDisposition.RETAIN)),
        _with_filler(terminal),  # type: ignore[arg-type]
    )
    with pytest.raises(WorkflowLegTransferConflict, match="cannot use that disposition"):
        _validate_package_inventory(
            _proposal(_plan(package_id, PackageTransferDisposition.CANCEL)),
            _with_filler(terminal),  # type: ignore[arg-type]
        )
    with pytest.raises(WorkflowLegTransferConflict, match="only finished active packages"):
        _validate_package_inventory(
            _proposal(_plan(package_id, PackageTransferDisposition.COMPLETE)),
            _with_filler(terminal),  # type: ignore[arg-type]
        )


def test_an_open_package_cannot_be_retained_and_needs_no_effort_left_to_complete() -> None:
    package_id = uuid4()

    with pytest.raises(WorkflowLegTransferConflict, match="only terminal packages"):
        _validate_package_inventory(
            _proposal(_plan(package_id, PackageTransferDisposition.RETAIN)),
            _with_filler(_row(package_id, "in_progress")),  # type: ignore[arg-type]
        )
    with pytest.raises(WorkflowLegTransferConflict, match="only finished active packages"):
        _validate_package_inventory(
            _proposal(_plan(package_id, PackageTransferDisposition.COMPLETE)),
            _with_filler(_row(package_id, "in_progress", remaining=90)),  # type: ignore[arg-type]
        )
    _validate_package_inventory(
        _proposal(_plan(package_id, PackageTransferDisposition.COMPLETE)),
        _with_filler(_row(package_id, "in_progress", remaining=0)),  # type: ignore[arg-type]
    )
    # A package with no recorded remaining effort counts as finished.
    _validate_package_inventory(
        _proposal(_plan(package_id, PackageTransferDisposition.COMPLETE)),
        _with_filler(_row(package_id, "in_progress", remaining=None)),  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    "dependent",
    [PackageTransferDisposition.CANCEL, PackageTransferDisposition.RETAIN],
)
def test_a_cancelled_predecessor_allows_only_a_safe_dependent(
    dependent: PackageTransferDisposition,
) -> None:
    predecessor, follower = uuid4(), uuid4()
    proposal = _proposal(
        _plan(predecessor, PackageTransferDisposition.CANCEL), _plan(follower, dependent)
    )

    _validate_dependency_dispositions(
        proposal,
        ({"package_id": follower, "predecessor_package_id": predecessor},),  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    "dependent",
    [PackageTransferDisposition.TRANSFER, PackageTransferDisposition.COMPLETE],
)
def test_a_cancelled_predecessor_refuses_a_continuing_dependent(
    dependent: PackageTransferDisposition,
) -> None:
    predecessor, follower = uuid4(), uuid4()
    proposal = _proposal(
        _plan(predecessor, PackageTransferDisposition.CANCEL), _plan(follower, dependent)
    )

    with pytest.raises(WorkflowLegTransferConflict, match="safe dependent disposition"):
        _validate_dependency_dispositions(
            proposal,
            ({"package_id": follower, "predecessor_package_id": predecessor},),  # type: ignore[arg-type]
        )


def test_dependencies_outside_the_proposal_are_ignored() -> None:
    planned = uuid4()
    proposal = _proposal(_plan(planned, PackageTransferDisposition.TRANSFER))

    _validate_dependency_dispositions(
        proposal,
        ({"package_id": planned, "predecessor_package_id": uuid4()},),  # type: ignore[arg-type]
    )
