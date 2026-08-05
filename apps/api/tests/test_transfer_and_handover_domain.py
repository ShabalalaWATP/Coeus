"""Evidence invariants for cross-team transfers and package handovers."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.domain.work_package_handovers import (
    ReservationDisposition,
    ReservationHandover,
    WorkPackageHandoverRequest,
)
from coeus.domain.workflow_leg_transfers import (
    PackageTransferDisposition,
    PackageTransferPlan,
    ProposeWorkflowLegTransfer,
    WorkflowLegTransferCommand,
    proposal_hash,
)

DIGEST = "a" * 64
START = datetime(2026, 8, 17, 9, tzinfo=UTC)
LATER = datetime.now(UTC) + timedelta(days=1)


def _transfer_plan(
    package_id: UUID | None = None,
    disposition: PackageTransferDisposition = PackageTransferDisposition.TRANSFER,
) -> PackageTransferPlan:
    identifier = package_id or uuid4()
    if disposition is not PackageTransferDisposition.TRANSFER:
        return PackageTransferPlan(identifier, disposition, 1)
    return PackageTransferPlan(
        identifier, disposition, 1, uuid4(), "reservation-1", START, START + timedelta(hours=2), 120
    )


def _proposal(**overrides: object) -> ProposeWorkflowLegTransfer:
    values: dict[str, object] = {
        "transfer_id": uuid4(),
        "ticket_id": uuid4(),
        "workflow_leg": WorkflowLeg.RFA,
        "source_unit_id": uuid4(),
        "target_unit_id": uuid4(),
        "target_user_id": uuid4(),
        "expected_ownership_version": 1,
        "expected_ticket_version": 1,
        "expected_ticket_source_hash": DIGEST,
        "authorising_grant_id": uuid4(),
        "expected_grant_version": 1,
        "expires_at": LATER,
        "packages": (_transfer_plan(),),
        "reason": "Synthetic cross-team transfer.",
    }
    values.update(overrides)
    return ProposeWorkflowLegTransfer(**values)  # type: ignore[arg-type]


def test_a_transfer_needs_two_distinct_teams_and_current_evidence() -> None:
    unit_id = uuid4()
    with pytest.raises(ValueError, match="distinct teams"):
        _proposal(source_unit_id=unit_id, target_unit_id=unit_id)
    with pytest.raises(ValueError, match="evidence versions must be positive"):
        _proposal(expected_ownership_version=0)
    with pytest.raises(ValueError, match="ticket source hash is invalid"):
        _proposal(expected_ticket_source_hash="short")
    with pytest.raises(ValueError, match="expires_at"):
        _proposal(expires_at=datetime(2026, 9, 1, 9))


def test_a_transfer_needs_a_bounded_unique_and_moving_package_set() -> None:
    package_id = uuid4()
    with pytest.raises(ValueError, match="between one and 64 package dispositions"):
        _proposal(packages=())
    with pytest.raises(ValueError, match="between one and 64 package dispositions"):
        _proposal(packages=tuple(_transfer_plan() for _ in range(65)))
    with pytest.raises(ValueError, match="dispositions must be unique"):
        _proposal(packages=(_transfer_plan(package_id), _transfer_plan(package_id)))
    with pytest.raises(ValueError, match="at least one package must transfer"):
        _proposal(packages=(_transfer_plan(disposition=PackageTransferDisposition.RETAIN),))


def test_a_transferring_package_needs_a_complete_reservation_plan() -> None:
    with pytest.raises(ValueError, match="complete reservation plan"):
        PackageTransferPlan(uuid4(), PackageTransferDisposition.TRANSFER, 1)
    with pytest.raises(ValueError, match="complete reservation plan"):
        PackageTransferPlan(uuid4(), PackageTransferDisposition.RETAIN, 1, uuid4())
    with pytest.raises(ValueError, match="package version must be positive"):
        PackageTransferPlan(uuid4(), PackageTransferDisposition.RETAIN, 0)


def test_the_proposal_hash_covers_the_actor_and_every_disposition() -> None:
    proposal = _proposal()
    actor = uuid4()

    assert proposal_hash(actor, proposal) == proposal_hash(actor, proposal)
    assert proposal_hash(actor, proposal) != proposal_hash(uuid4(), proposal)
    assert proposal_hash(actor, proposal) != proposal_hash(
        actor, _proposal(reason="A different reason entirely.")
    )


@pytest.mark.parametrize("action", ["accept", "reject", "cancel", "expire"])
def test_every_reviewed_transfer_action_is_accepted(action: str) -> None:
    command = WorkflowLegTransferCommand(uuid4(), "key-1", uuid4(), uuid4(), 1, action)

    assert command.action == action


def test_an_unknown_transfer_action_or_stale_version_is_refused() -> None:
    with pytest.raises(ValueError, match="transfer command is invalid"):
        WorkflowLegTransferCommand(uuid4(), "key-1", uuid4(), uuid4(), 1, "delete")
    with pytest.raises(ValueError, match="transfer command is invalid"):
        WorkflowLegTransferCommand(uuid4(), "key-1", uuid4(), uuid4(), 0, "accept")
    with pytest.raises(ValueError, match="idempotency_key"):
        WorkflowLegTransferCommand(uuid4(), " key ", uuid4(), uuid4(), 1, "accept")


def _handover(**overrides: object) -> WorkPackageHandoverRequest:
    values: dict[str, object] = {
        "unit_id": uuid4(),
        "package_id": uuid4(),
        "target_user_id": uuid4(),
        "expected_package_version": 1,
        "expected_ownership_version": 1,
        "authorising_grant_id": uuid4(),
        "expected_grant_version": 1,
        "target_membership_id": uuid4(),
        "expected_target_membership_version": 1,
        "expected_target_account_credential_version": 0,
        "expected_target_account_source_hash": DIGEST,
        "expected_ticket_version": 1,
        "expected_ticket_source_hash": DIGEST,
        "reservations": (),
    }
    values.update(overrides)
    return WorkPackageHandoverRequest(**values)  # type: ignore[arg-type]


def test_a_handover_needs_positive_versions_and_hexadecimal_hashes() -> None:
    assert _handover().expected_target_account_credential_version == 0
    with pytest.raises(ValueError, match="handover evidence versions are invalid"):
        _handover(expected_ticket_version=0)
    with pytest.raises(ValueError, match="handover evidence versions are invalid"):
        _handover(expected_target_account_credential_version=-1)
    with pytest.raises(ValueError, match="target account source hash is invalid"):
        _handover(expected_target_account_source_hash="z" * 64)
    with pytest.raises(ValueError, match="ticket source hash is invalid"):
        _handover(expected_ticket_source_hash="b" * 63)


def _reservation(source_id: UUID | None = None, replacement: bool = False) -> ReservationHandover:
    identifier = source_id or uuid4()
    if not replacement:
        return ReservationHandover(identifier, 1, ReservationDisposition.RELEASE)
    return ReservationHandover(
        identifier, 1, ReservationDisposition.REPLACE, uuid4(), "replacement-key"
    )


def test_handover_reservations_stay_bounded_and_uniquely_identified() -> None:
    source_id = uuid4()
    assert (
        len(_handover(reservations=(_reservation(), _reservation(replacement=True))).reservations)
        == 2
    )
    with pytest.raises(ValueError, match="reservation inventory is too large"):
        _handover(reservations=tuple(_reservation() for _ in range(65)))
    with pytest.raises(ValueError, match="reservation identities must be unique"):
        _handover(reservations=(_reservation(source_id), _reservation(source_id)))


def test_a_replacement_reservation_needs_both_an_identity_and_a_key() -> None:
    with pytest.raises(ValueError, match="replacement reservation identity"):
        ReservationHandover(uuid4(), 1, ReservationDisposition.REPLACE)
    with pytest.raises(ValueError, match="replacement idempotency key"):
        ReservationHandover(uuid4(), 1, ReservationDisposition.REPLACE, uuid4())
    with pytest.raises(ValueError, match="replacement reservation identity"):
        ReservationHandover(uuid4(), 1, ReservationDisposition.RELEASE, uuid4(), "key")
    with pytest.raises(ValueError, match="source reservation version must be positive"):
        ReservationHandover(uuid4(), 0, ReservationDisposition.RELEASE)
