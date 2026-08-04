"""Transactional branch guards for organisation personnel persistence."""

from dataclasses import replace
from datetime import timedelta
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import RowMapping

from coeus.domain.organisation_deactivation import (
    OrganisationDeactivationConflict,
    OrganisationDeactivationImpact,
    deactivation_hash,
)
from coeus.domain.organisation_membership import MembershipOperation
from coeus.domain.organisation_transfer import (
    PersonnelTransferConflict,
    PersonnelTransferResult,
    PersonnelTransferStatus,
)
from coeus.persistence import organisation_deactivation_postgres as deactivate
from coeus.persistence import organisation_membership_postgres as membership
from coeus.persistence import organisation_transfer_postgres as transfer
from test_organisation_persistence_branch_guards_b import (
    NOW,
    _Connection,
    _deactivation_command,
    _Engine,
    _membership_command,
    _Result,
    _transfer_command,
)


def test_membership_replay_rejects_payload_collision() -> None:
    command = _membership_command(MembershipOperation.CREATE)
    request = command.request
    row = {
        "command_id": command.command_id,
        "idempotency_key": command.idempotency_key,
        "request_hash": "b" * 64,
        "actor_user_id": command.actor_user_id,
        "membership_id": request.membership_id,
        "user_id": request.user_id,
        "unit_id": request.unit_id,
        "authorising_grant_id": request.authorising_grant_id,
        "operation": request.operation.value,
        "expected_version": request.expected_version,
        "role": request.role.value,
        "assignment_eligible": request.assignment_eligible,
        "valid_from": request.valid_from,
        "valid_until": request.valid_until,
        "reason_hash": "irrelevant",
    }
    with pytest.raises(membership.MembershipIdempotencyConflict):
        membership._replay((cast(RowMapping, row),), command)


def test_deactivation_replay_rejects_payload_collision() -> None:
    command = _deactivation_command()
    row = {
        "command_id": command.command_id,
        "idempotency_key": command.idempotency_key,
        "request_hash": "b" * 64,
    }
    with pytest.raises(deactivate.OrganisationDeactivationIdempotencyConflict):
        deactivate._replay((cast(RowMapping, row),), command)


def test_transfer_schedule_rejects_non_future_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _transfer_command()
    monkeypatch.setattr(transfer, "_locks", lambda *_: None)
    monkeypatch.setattr(transfer, "_load_command", lambda *_: ())
    monkeypatch.setattr(transfer, "transaction_time", lambda *_: command.request.effective_at)
    store = transfer.PostgresOrganisationTransferStore(_Engine(_Connection()))  # type: ignore[arg-type]
    with pytest.raises(PersonnelTransferConflict, match="boundary must be in the future"):
        store._schedule_once(command)


def test_transfer_schedule_rejects_existing_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _transfer_command()
    monkeypatch.setattr(transfer, "_locks", lambda *_: None)
    monkeypatch.setattr(transfer, "_load_command", lambda *_: ())
    monkeypatch.setattr(transfer, "transaction_time", lambda *_: NOW)
    monkeypatch.setattr(transfer, "_validate", lambda *_: None)
    connection = _Connection(_Result(), _Result(rows=({},)))
    store = transfer.PostgresOrganisationTransferStore(_Engine(connection))  # type: ignore[arg-type]
    with pytest.raises(PersonnelTransferConflict, match="pending transfer"):
        store._schedule_once(command)


def test_transfer_activation_rejects_stale_source(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _transfer_command()
    pending = PersonnelTransferResult(
        command.command_id,
        command.request.source_membership_id,
        command.request.target_membership_id,
        PersonnelTransferStatus.PENDING,
        1,
        0,
    )
    monkeypatch.setattr(transfer, "_locks", lambda *_: None)
    monkeypatch.setattr(transfer, "_locked_transfer", lambda *_: {})
    monkeypatch.setattr(transfer, "replay", lambda *_: pending)
    monkeypatch.setattr(
        transfer, "transaction_time", lambda *_: command.request.effective_at + timedelta(seconds=1)
    )
    monkeypatch.setattr(transfer, "_validate", lambda *_: None)
    connection = _Connection(_Result(), _Result(scalar=None))
    store = transfer.PostgresOrganisationTransferStore(_Engine(connection))  # type: ignore[arg-type]
    with pytest.raises(PersonnelTransferConflict, match="source membership changed"):
        store._activate_once(command)


def _deactivation_impact(*, blocking: bool = False) -> OrganisationDeactivationImpact:
    return OrganisationDeactivationImpact(
        0, 0, 1 if blocking else 0, 0, 0, 0, 0, 0, 0, 0, 0, "b" * 64
    )


def _patch_deactivation_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deactivate, "_locks", lambda *_: None)
    monkeypatch.setattr(deactivate, "_load_command", lambda *_: ())
    monkeypatch.setattr(deactivate, "transaction_time", lambda *_: NOW)
    monkeypatch.setattr(deactivate, "lock_lineages", lambda *_: None)
    monkeypatch.setattr(deactivate, "validate_lineage", lambda *_: None)


def test_deactivation_apply_rejects_changed_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _deactivation_command()
    _patch_deactivation_apply(monkeypatch)
    store = deactivate.PostgresOrganisationDeactivationStore(
        _Engine(_Connection(_Result(), _Result()))
    )  # type: ignore[arg-type]
    with pytest.raises(OrganisationDeactivationConflict, match="unit changed"):
        store._apply_once(command)


@pytest.mark.parametrize("blocking", (False, True))
def test_deactivation_apply_rechecks_preview_and_dependencies(
    monkeypatch: pytest.MonkeyPatch, blocking: bool
) -> None:
    command = _deactivation_command()
    impact = _deactivation_impact(blocking=blocking)
    if blocking:
        command = replace(
            command,
            preview_hash=deactivation_hash(command.request, command.actor_user_id, impact),
        )
    _patch_deactivation_apply(monkeypatch)
    monkeypatch.setattr(deactivate, "_impact", lambda *_: impact)
    unit = {"is_active": True, "parent_unit_id": uuid4(), "version": 1}
    store = deactivate.PostgresOrganisationDeactivationStore(
        _Engine(_Connection(_Result(), _Result(rows=(unit,))))
    )  # type: ignore[arg-type]
    message = "dependent records" if blocking else "preview is stale"
    with pytest.raises(OrganisationDeactivationConflict, match=message):
        store._apply_once(command)
