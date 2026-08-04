from contextlib import AbstractContextManager
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection, Engine

from coeus.domain.organisation import (
    DeliveryRoute,
    FindingSeverity,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    OrganisationReconciliationCheckpoint,
    OrganisationReconciliationFinding,
    OrganisationTopologyRevision,
    OrganisationUnit,
    ReconciliationStatus,
    TeamCapabilityCoverage,
    TeamDeliveryProfile,
    TeamMembership,
)
from coeus.domain.organisation_reconciliation import OrganisationReconciliationPlan
from coeus.persistence.organisation_reconciliation_postgres import (
    PostgresOrganisationReconciliation,
    _already_applied,
    _end_absent_memberships,
    _reconcile_membership,
    _required_upsert,
    _upsert_root_unit,
)
from coeus.persistence.organisation_schema import ensure_organisation_schema

NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)


class FakeResult:
    def __init__(
        self,
        first: object = (1,),
        *,
        rows: list[dict[str, object]] | None = None,
    ) -> None:
        self._first = first
        self._rows = rows or []

    def first(self) -> object:
        return self._first

    def mappings(self) -> "FakeResult":
        return self

    def all(self) -> list[dict[str, object]]:
        return self._rows

    def one(self) -> dict[str, object]:
        return self._rows[0]


class FakeConnection:
    def __init__(self) -> None:
        self.mode = "happy"
        self.statements: list[str] = []
        self.checkpoint_id = uuid4()
        self.ended_user_id = uuid4()
        self.ended_unit_id = uuid4()

    def execute(self, statement: object, params: object = None) -> FakeResult:
        sql = str(statement)
        self.statements.append(sql)
        if "FROM organisation_reconciliation_checkpoints" in sql:
            if "ORDER BY completed_at" in sql:
                return FakeResult({"checkpoint_id": self.checkpoint_id})
            if self.mode == "completed":
                return FakeResult(
                    {
                        "source_namespace": "legacy-flat-teams-v1",
                        "source_digest": "a" * 64,
                        "status": "completed",
                    }
                )
            if self.mode == "checkpoint_conflict":
                return FakeResult(
                    {"source_namespace": "other", "source_digest": "b" * 64, "status": "running"}
                )
            return FakeResult(None)
        if "SELECT membership_id FROM team_memberships" in sql:
            return FakeResult((uuid4(),) if self.mode == "future_absence" else None)
        if "SELECT 1 FROM team_capability_coverage coverage" in sql:
            return FakeResult(None)
        if "UNION ALL SELECT 1 FROM team_delivery_profiles" in sql:
            return FakeResult(None)
        if "NOT (membership_id = ANY" in sql and "LIMIT 1" in sql:
            return FakeResult(None)
        if "SELECT state, valid_until FROM team_memberships" in sql:
            return FakeResult(None)
        if "SELECT * FROM organisation_units" in sql:
            return FakeResult(None)
        if "SELECT * FROM team_delivery_profiles" in sql:
            return FakeResult(None)
        if "SELECT * FROM team_capability_coverage" in sql:
            return FakeResult(None)
        if "UPDATE team_memberships SET state = 'ended'" in sql:
            return FakeResult(rows=[{"user_id": self.ended_user_id, "unit_id": self.ended_unit_id}])
        if "SELECT user_id, unit_id, role, state" in sql:
            if self.mode.startswith("existing_"):
                state = self.mode.removeprefix("existing_")
                return FakeResult(
                    {
                        "user_id": cast(dict[str, object], params)["membership_id"],
                        "unit_id": uuid4(),
                        "state": state,
                        "valid_from": NOW,
                        "version": 2,
                    }
                )
            return FakeResult(None)
        if self.mode == "upsert_conflict" and "ON CONFLICT" in sql:
            return FakeResult(None)
        return FakeResult()


class FakeBegin(AbstractContextManager[FakeConnection]):
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def __enter__(self) -> FakeConnection:
        return self.connection

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class FakeEngine:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def begin(self) -> FakeBegin:
        return FakeBegin(self.connection)


def _plan() -> OrganisationReconciliationPlan:
    actor_id = uuid4()
    unit = OrganisationUnit(
        uuid4(), "Synthetic Team", "Team", OrganisationCategory.DELIVERY_TEAM, None, NOW
    )
    revision = OrganisationTopologyRevision(
        uuid4(), unit.unit_id, None, (unit.unit_id,), NOW, uuid4(), actor_id
    )
    profile = TeamDeliveryProfile(uuid4(), unit.unit_id, DeliveryRoute.RFA, 5, 37.0)
    coverage = TeamCapabilityCoverage(uuid4(), profile.profile_id, "imagery", 3, NOW, actor_id)
    membership = TeamMembership(
        uuid4(),
        uuid4(),
        unit.unit_id,
        MembershipRole.MEMBER,
        MembershipState.ACTIVE,
        True,
        NOW,
        actor_id,
        "Synthetic posting",
        "legacy-flat-teams-v1",
    )
    checkpoint = OrganisationReconciliationCheckpoint(
        uuid4(),
        "legacy-flat-teams-v1",
        "a" * 64,
        ReconciliationStatus.COMPLETED,
        NOW,
        {},
        NOW,
    )
    finding = OrganisationReconciliationFinding(
        uuid4(), checkpoint.checkpoint_id, "synthetic", FindingSeverity.WARNING, "user", {}, NOW
    )
    return OrganisationReconciliationPlan(
        checkpoint,
        actor_id,
        NOW,
        ((unit, revision),),
        (profile,),
        (coverage,),
        (membership,),
        (finding,),
    )


def test_atomic_committer_writes_every_projection_and_short_circuits_replay() -> None:
    connection = FakeConnection()
    committer = PostgresOrganisationReconciliation(cast(Engine, FakeEngine(connection)))
    committer.apply_reconciliation(_plan())
    assert any("pg_advisory_xact_lock" in statement for statement in connection.statements)
    assert any("coeus_audit_events" in statement for statement in connection.statements)
    assert any("coeus_outbox" in statement for statement in connection.statements)
    assert any("effective_authority_epochs" in statement for statement in connection.statements)

    connection.statements.clear()
    connection.mode = "completed"
    replay = _plan()
    connection.checkpoint_id = replay.checkpoint.checkpoint_id
    committer.apply_reconciliation(replay)
    assert not any("coeus_audit_events" in statement for statement in connection.statements)


def test_checkpoint_and_absent_membership_conflicts_fail_closed() -> None:
    plan = _plan()
    connection = FakeConnection()
    connection.mode = "checkpoint_conflict"
    with pytest.raises(ValueError, match="checkpoint identity"):
        _already_applied(cast(Connection, connection), plan)
    connection.mode = "future_absence"
    with pytest.raises(ValueError, match="before its start"):
        _end_absent_memberships(cast(Connection, connection), plan)


def test_root_and_required_upsert_conflicts_fail_closed() -> None:
    plan = _plan()
    connection = FakeConnection()
    child = replace_unit_parent(plan.units[0][0])
    with pytest.raises(ValueError, match="flat root"):
        _upsert_root_unit(cast(Connection, connection), child, plan.units[0][1])
    connection.mode = "upsert_conflict"
    with pytest.raises(ValueError, match="unit identity"):
        _upsert_root_unit(cast(Connection, connection), plan.units[0][0], plan.units[0][1])
    with pytest.raises(ValueError, match="profile identity"):
        _required_upsert(
            cast(Connection, connection),
            "INSERT ON CONFLICT",
            plan.delivery_profiles[0],
            "profile",
        )


def test_membership_reconciliation_rejects_terminal_and_conflicting_rows() -> None:
    membership = _plan().memberships[0]
    connection = FakeConnection()
    connection.mode = "existing_ended"
    with pytest.raises(ValueError, match="explicit new posting"):
        _reconcile_membership(cast(Connection, connection), membership)
    connection.mode = "upsert_conflict"
    with pytest.raises(ValueError, match="stored authority"):
        _reconcile_membership(cast(Connection, connection), membership)


def test_runtime_schema_helper_executes_every_migration_statement() -> None:
    connection = FakeConnection()
    ensure_organisation_schema(cast(Connection, connection))
    assert len(connection.statements) > 10


def replace_unit_parent(unit: OrganisationUnit) -> OrganisationUnit:
    return OrganisationUnit(
        unit.unit_id,
        unit.name,
        unit.short_name,
        unit.category,
        uuid4(),
        unit.valid_from,
    )
