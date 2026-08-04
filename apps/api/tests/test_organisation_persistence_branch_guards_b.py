"""Branch guards for membership, transfer and deactivation persistence."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection

from coeus.domain.organisation import MembershipRole, OrganisationCategory
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.organisation_deactivation import (
    OrganisationDeactivationCommand,
    OrganisationDeactivationConflict,
    OrganisationDeactivationRequest,
)
from coeus.domain.organisation_membership import (
    MembershipCommandConflict,
    MembershipMutationCommand,
    MembershipMutationRequest,
    MembershipMutationSnapshot,
    MembershipOperation,
)
from coeus.domain.organisation_transfer import (
    PersonnelTransferCommand,
    PersonnelTransferConflict,
    PersonnelTransferDenied,
    PersonnelTransferImpact,
    PersonnelTransferRequest,
    personnel_transfer_hash,
)
from coeus.persistence import organisation_deactivation_postgres as deactivate
from coeus.persistence import organisation_membership_postgres as membership
from coeus.persistence import organisation_transfer_postgres as transfer

NOW = datetime(2026, 8, 4, 10, tzinfo=UTC)


class _Result:
    def __init__(self, *, rows: tuple[dict[str, object], ...] = (), scalar: object = None) -> None:
        self.rows = rows
        self.scalar = scalar

    def mappings(self) -> "_Result":
        return self

    def first(self) -> object:
        return self.rows[0] if self.rows else None

    def one(self) -> object:
        return self.rows[0]

    def scalar_one_or_none(self) -> object:
        return self.scalar

    def scalar_one(self) -> object:
        return self.scalar

    def all(self) -> list[object]:
        return list(self.rows)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.rows)


class _Connection:
    def __init__(self, *results: _Result) -> None:
        self.results = list(results)

    def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return self.results.pop(0) if self.results else _Result()


def _membership_command(operation: MembershipOperation) -> MembershipMutationCommand:
    valid_until = NOW if operation is MembershipOperation.END else None
    request = MembershipMutationRequest(
        operation,
        uuid4(),
        uuid4(),
        uuid4(),
        0 if operation is MembershipOperation.CREATE else 1,
        MembershipRole.MEMBER,
        operation is not MembershipOperation.END,
        NOW - timedelta(days=2),
        valid_until,
        uuid4(),
        "Synthetic membership guard.",
    )
    return MembershipMutationCommand(uuid4(), f"membership-{operation}", uuid4(), request, "a" * 64)


@pytest.mark.parametrize("unit", (None, {"is_active": False}))
def test_membership_authority_rejects_missing_or_inactive_unit(unit: object) -> None:
    command = _membership_command(MembershipOperation.CREATE)
    rows = () if unit is None else (cast(dict[str, object], unit),)
    with pytest.raises(MembershipCommandConflict, match="unit is not active"):
        membership._validate_authority(
            cast(Connection, _Connection(_Result(rows=rows))), command, NOW
        )


def test_membership_authority_rejects_future_end() -> None:
    command = _membership_command(MembershipOperation.END)
    command = replace(
        command, request=replace(command.request, valid_until=NOW + timedelta(days=1))
    )
    with pytest.raises(MembershipCommandConflict, match="future membership endings"):
        membership._validate_authority(
            cast(Connection, _Connection(_Result(rows=({"is_active": True},)))), command, NOW
        )


def test_membership_snapshot_requires_unit() -> None:
    with pytest.raises(MembershipCommandConflict, match="unit is unavailable"):
        membership._snapshot(
            cast(Connection, _Connection(_Result())),
            _membership_command(MembershipOperation.CREATE).request,
        )


def test_membership_create_rejects_overlap() -> None:
    command = _membership_command(MembershipOperation.CREATE)
    with pytest.raises(MembershipCommandConflict, match="overlapping"):
        membership._mutate(cast(Connection, _Connection(_Result(rows=({},)))), command, NOW)


@pytest.mark.parametrize(
    "operation", (MembershipOperation.CREATE, MembershipOperation.UPDATE, MembershipOperation.END)
)
def test_membership_mutations_fail_closed_on_stale_write(operation: MembershipOperation) -> None:
    command = _membership_command(operation)
    results = (
        (_Result(), _Result(scalar=None))
        if operation is MembershipOperation.CREATE
        else (_Result(scalar=None),)
    )
    with pytest.raises(MembershipCommandConflict, match="identity or version is stale"):
        membership._mutate(cast(Connection, _Connection(*results)), command, NOW)


def test_membership_apply_rejects_stale_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _membership_command(MembershipOperation.CREATE)
    snapshot = MembershipMutationSnapshot(1, 0, 0, "b" * 64)
    monkeypatch.setattr(membership, "_locks", lambda *_: None)
    monkeypatch.setattr(membership, "_load_command", lambda *_: ())
    monkeypatch.setattr(membership, "transaction_time", lambda *_: NOW)
    monkeypatch.setattr(membership, "_validate_authority", lambda *_: None)
    monkeypatch.setattr(membership, "_snapshot", lambda *_: snapshot)
    store = membership.PostgresOrganisationMembershipStore(_Engine(_Connection()))  # type: ignore[arg-type]
    with pytest.raises(MembershipCommandConflict, match="preview is stale"):
        store._apply_once(command)


class _Begin:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def __enter__(self) -> _Connection:
        return self.connection

    def __exit__(self, *_args: object) -> None:
        return None


class _Engine:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def begin(self) -> _Begin:
        return _Begin(self.connection)


def _transfer_command() -> PersonnelTransferCommand:
    request = PersonnelTransferRequest(
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        1,
        1,
        MembershipRole.MEMBER,
        True,
        NOW + timedelta(days=1),
        uuid4(),
        uuid4(),
        "Synthetic transfer guard.",
    )
    return PersonnelTransferCommand(uuid4(), "transfer-guard", uuid4(), request, "a" * 64)


def _transfer_impact() -> PersonnelTransferImpact:
    return PersonnelTransferImpact(0, 0, 0, 0, "b" * 64)


def _transfer_row(_command: PersonnelTransferCommand) -> dict[str, object]:
    return {
        "source_version": 1,
        "source_state": "active",
        "source_valid_until": None,
        "source_valid_from": NOW - timedelta(days=1),
        "target_active": True,
        "target_version": 1,
        "target_category": OrganisationCategory.DELIVERY_TEAM.value,
    }


def test_transfer_rejects_stale_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _transfer_command()
    monkeypatch.setattr(transfer, "_impact", lambda *_: _transfer_impact())
    with pytest.raises(PersonnelTransferConflict, match="preview is stale"):
        transfer._validate(cast(Connection, _Connection()), command, NOW)


def test_transfer_rejects_changed_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _transfer_command()
    impact = _transfer_impact()
    command = PersonnelTransferCommand(
        command.command_id,
        command.idempotency_key,
        command.actor_user_id,
        command.request,
        personnel_transfer_hash(command.request, command.actor_user_id, impact),
    )
    monkeypatch.setattr(transfer, "_impact", lambda *_: impact)
    row = {**_transfer_row(command), "target_active": False}
    with pytest.raises(PersonnelTransferConflict, match="endpoints changed"):
        transfer._validate(cast(Connection, _Connection(_Result(rows=(row,)))), command, NOW)


def test_transfer_rejects_overlap(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _transfer_command()
    impact = _transfer_impact()
    command = PersonnelTransferCommand(
        command.command_id,
        command.idempotency_key,
        command.actor_user_id,
        command.request,
        personnel_transfer_hash(command.request, command.actor_user_id, impact),
    )
    monkeypatch.setattr(transfer, "_impact", lambda *_: impact)
    connection = cast(
        Connection, _Connection(_Result(rows=(_transfer_row(command),)), _Result(rows=({},)))
    )
    with pytest.raises(PersonnelTransferConflict, match="overlaps"):
        transfer._validate(connection, command, NOW)


def test_transfer_wraps_expired_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _transfer_command()
    impact = _transfer_impact()
    command = PersonnelTransferCommand(
        command.command_id,
        command.idempotency_key,
        command.actor_user_id,
        command.request,
        personnel_transfer_hash(command.request, command.actor_user_id, impact),
    )
    monkeypatch.setattr(transfer, "_impact", lambda *_: impact)
    monkeypatch.setattr(transfer, "lock_lineages", lambda *_: None)
    monkeypatch.setattr(
        transfer,
        "validate_lineage",
        lambda *_: (_ for _ in ()).throw(OrganisationAuthorityDenied("expired")),
    )
    connection = cast(Connection, _Connection(_Result(rows=(_transfer_row(command),)), _Result()))
    with pytest.raises(PersonnelTransferDenied, match="no longer effective"):
        transfer._validate(connection, command, NOW)


def test_transfer_impact_requires_endpoints() -> None:
    with pytest.raises(PersonnelTransferConflict, match="endpoints are unavailable"):
        transfer._impact(cast(Connection, _Connection(_Result())), _transfer_command().request)


def _deactivation_command() -> OrganisationDeactivationCommand:
    return OrganisationDeactivationCommand(
        uuid4(),
        "deactivate-guard",
        uuid4(),
        OrganisationDeactivationRequest(uuid4(), 1, uuid4(), "Synthetic deactivation guard."),
        "a" * 64,
    )


def test_deactivation_impact_requires_unit() -> None:
    with pytest.raises(OrganisationDeactivationConflict, match="unit is unavailable"):
        deactivate._impact(
            cast(Connection, _Connection(_Result())), _deactivation_command().request
        )
