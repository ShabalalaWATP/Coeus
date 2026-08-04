from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import Engine, RowMapping

from coeus.domain.organisation import (
    DeliveryRoute,
    EffectiveAuthorityEpoch,
    FindingSeverity,
    ManagementAction,
    MembershipRole,
    MembershipState,
    OrganisationCategory,
    OrganisationManagementGrant,
    OrganisationReconciliationCheckpoint,
    OrganisationReconciliationFinding,
    OrganisationTopologyRevision,
    OrganisationUnit,
    ReconciliationStatus,
    TeamCapabilityCoverage,
    TeamDeliveryProfile,
    TeamMembership,
)
from coeus.persistence.organisation_postgres import (
    PostgresOrganisationRepository,
    _depth,
    _grant,
    _limit,
    _membership,
    _params,
)
from coeus.persistence.organisation_rows import decode_unit as _unit

NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)


class Result:
    def __init__(
        self,
        first: object = (1,),
        *,
        rows: list[dict[str, object]] | None = None,
        scalars: list[object] | None = None,
    ) -> None:
        self.first_value = first
        self.rows = rows or []
        self.scalar_values = scalars or []

    def first(self) -> object:
        return self.first_value

    def mappings(self) -> "Result":
        return self

    def one(self) -> dict[str, object]:
        return self.rows[0]

    def scalars(self) -> list[object]:
        return self.scalar_values

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.rows)


class Connection:
    def __init__(self, *results: Result) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, object]] = []

    def execute(self, statement: object, params: object = None) -> Result:
        self.calls.append((str(statement), params))
        return self.results.pop(0) if self.results else Result()


class Begin(AbstractContextManager[Connection]):
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def __enter__(self) -> Connection:
        return self.connection

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class FakeEngine:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def begin(self) -> Begin:
        return Begin(self.connection)


def _repository(*results: Result) -> tuple[PostgresOrganisationRepository, Connection]:
    connection = Connection(*results)
    return PostgresOrganisationRepository(cast(Engine, FakeEngine(connection))), connection


def _unit_record(unit_id: UUID | None = None, parent_id: UUID | None = None) -> dict[str, object]:
    return {
        "unit_id": unit_id or uuid4(),
        "name": "Synthetic Unit",
        "short_name": "SU",
        "category": "delivery_team",
        "parent_unit_id": parent_id,
        "valid_from": NOW,
        "valid_until": None,
        "time_zone": "Europe/London",
        "description": "Synthetic fixture",
        "is_active": True,
        "version": 1,
        "provenance": "manual",
    }


def _membership_record() -> dict[str, object]:
    return {
        "membership_id": uuid4(),
        "user_id": uuid4(),
        "unit_id": uuid4(),
        "role": "member",
        "state": "active",
        "assignment_eligible": True,
        "valid_from": NOW,
        "created_by_user_id": uuid4(),
        "reason": "Synthetic fixture",
        "provenance": "test",
        "valid_until": None,
        "version": 1,
    }


def _grant_record() -> dict[str, object]:
    return {
        "grant_id": uuid4(),
        "manager_user_id": uuid4(),
        "root_unit_id": uuid4(),
        "action": "task:assign",
        "include_descendants": True,
        "valid_from": NOW,
        "created_by_user_id": uuid4(),
        "reason": "Synthetic fixture",
        "valid_until": None,
        "revoked_at": None,
        "source_grant_id": None,
        "delegation_depth": 0,
        "version": 1,
    }


def test_read_queries_convert_rows_and_validate_limits() -> None:
    unit_row = _unit_record()
    membership_row = _membership_record()
    grant_row = _grant_record()
    repository, connection = _repository(
        Result(rows=[unit_row], first=unit_row),
        *(Result(rows=[unit_row]) for _ in range(4)),
        Result(rows=[membership_row]),
        Result(rows=[membership_row], first=membership_row),
        Result(rows=[grant_row]),
    )
    unit_id = cast(UUID, unit_row["unit_id"])
    user_id = cast(UUID, membership_row["user_id"])

    assert repository.get_unit(unit_id) is not None
    assert repository.list_roots(limit=1)[0].unit_id == unit_id
    assert repository.list_children(unit_id, limit=1)[0].unit_id == unit_id
    assert repository.list_ancestors(unit_id, maximum_depth=1)[0].unit_id == unit_id
    assert repository.list_descendants(unit_id, maximum_depth=1, limit=1)[0].unit_id == unit_id
    assert repository.list_memberships(user_id)[0].user_id == user_id
    assert repository.effective_membership(user_id, NOW) is not None
    assert repository.effective_grants(user_id, NOW)[0].action is ManagementAction.TASK_ASSIGN
    assert len(connection.calls) == 8
    assert _depth(0) == 0
    assert _limit(1, 1) == 1
    with pytest.raises(ValueError, match="maximum_depth"):
        repository.list_ancestors(unit_id, maximum_depth=13)
    with pytest.raises(ValueError, match="limit"):
        repository.list_roots(limit=0)


def test_empty_reads_and_row_converters_cover_optional_values() -> None:
    repository, _ = _repository(Result(first=None), Result(first=None))
    assert repository.get_unit(uuid4()) is None
    assert repository.effective_membership(uuid4(), NOW) is None
    unit_row = _unit_record(parent_id=uuid4())
    unit_row["valid_until"] = NOW + timedelta(days=1)
    grant_row = _grant_record()
    grant_row["source_grant_id"] = uuid4()
    grant_row["delegation_depth"] = 1
    grant_row["valid_until"] = NOW + timedelta(days=2)
    grant_row["revoked_at"] = NOW + timedelta(days=1)
    assert _unit(cast(RowMapping, unit_row)).parent_unit_id is not None
    assert _membership(cast(RowMapping, _membership_record())).state is MembershipState.ACTIVE
    assert _grant(cast(RowMapping, grant_row)).source_grant_id is not None


def test_simple_upserts_serialise_enums_paths_and_json() -> None:
    actor_id, unit_id = uuid4(), uuid4()
    membership = TeamMembership(
        uuid4(),
        uuid4(),
        unit_id,
        MembershipRole.MEMBER,
        MembershipState.ACTIVE,
        True,
        NOW,
        actor_id,
        "Synthetic fixture",
        "test",
    )
    grant = OrganisationManagementGrant(
        uuid4(),
        actor_id,
        unit_id,
        ManagementAction.TASK_ASSIGN,
        True,
        NOW,
        actor_id,
        "Synthetic fixture",
    )
    profile = TeamDeliveryProfile(uuid4(), unit_id, DeliveryRoute.RFA, 3, 37.0)
    coverage = TeamCapabilityCoverage(uuid4(), profile.profile_id, "imagery", 3, NOW, actor_id)
    epoch = EffectiveAuthorityEpoch(actor_id, unit_id, 1, NOW)
    checkpoint = OrganisationReconciliationCheckpoint(
        uuid4(), "test", "a" * 64, ReconciliationStatus.COMPLETED, NOW, {"page": 1}, NOW
    )
    finding = OrganisationReconciliationFinding(
        uuid4(),
        checkpoint.checkpoint_id,
        "test",
        FindingSeverity.INFO,
        "fixture",
        {"ok": True},
        NOW,
    )
    repository, connection = _repository(*(Result() for _ in range(7)))
    repository.upsert_membership(membership)
    repository.upsert_management_grant(grant)
    repository.upsert_delivery_profile(profile)
    repository.upsert_capability_coverage(coverage)
    repository.upsert_authority_epoch(epoch)
    repository.upsert_checkpoint(checkpoint)
    repository.upsert_finding(finding)
    assert _params(grant)["action"] == "task:assign"
    assert connection.calls[-2][1]["cursor"] == '{"page": 1}'  # type: ignore[index]
    assert connection.calls[-1][1]["details"] == '{"ok": true}'  # type: ignore[index]


def test_upserts_fail_closed_on_stale_identity() -> None:
    actor_id, unit_id = uuid4(), uuid4()
    membership = TeamMembership(
        uuid4(),
        uuid4(),
        unit_id,
        MembershipRole.MEMBER,
        MembershipState.ACTIVE,
        True,
        NOW,
        actor_id,
        "Synthetic fixture",
        "test",
    )
    checkpoint = OrganisationReconciliationCheckpoint(
        uuid4(), "test", "a" * 64, ReconciliationStatus.COMPLETED, NOW, {}, NOW
    )
    finding = OrganisationReconciliationFinding(
        uuid4(), checkpoint.checkpoint_id, "test", FindingSeverity.INFO, "fixture", {}, NOW
    )
    for action, label in (
        (lambda repo: repo.upsert_membership(membership), "membership identity"),
        (lambda repo: repo.upsert_checkpoint(checkpoint), "checkpoint identity"),
        (lambda repo: repo.upsert_finding(finding), "finding identity"),
    ):
        repository, _ = _repository(Result(first=None))
        with pytest.raises(ValueError, match=label):
            action(repository)


def test_unit_upsert_checks_identity_path_parent_and_revision() -> None:
    actor_id = uuid4()
    root = OrganisationUnit(
        uuid4(), "Synthetic Root", "Root", OrganisationCategory.COMMAND, None, NOW
    )
    root_revision = OrganisationTopologyRevision(
        uuid4(), root.unit_id, None, (root.unit_id,), NOW, uuid4(), actor_id
    )
    repository, connection = _repository(Result(first=None), Result(), Result(), Result())
    repository.upsert_unit(root, root_revision)
    assert any("organisation_topology_revisions" in call[0] for call in connection.calls)

    child = replace(root, unit_id=uuid4(), parent_unit_id=root.unit_id)
    child_revision = OrganisationTopologyRevision(
        uuid4(), child.unit_id, root.unit_id, (root.unit_id, child.unit_id), NOW, uuid4(), actor_id
    )
    repository, _ = _repository(
        Result(scalars=[root.unit_id]),
        Result(first=None),
        Result(),
        Result(),
        Result(),
        Result(),
        Result(),
    )
    repository.upsert_unit(child, child_revision)

    other_id = uuid4()
    other_revision = replace(root_revision, unit_id=other_id, path=(other_id,))
    with pytest.raises(ValueError, match="identities"):
        repository.upsert_unit(root, other_revision)
    repository, _ = _repository(Result(scalars=[]))
    with pytest.raises(ValueError, match="parent closure"):
        repository.upsert_unit(child, child_revision)
    repository, _ = _repository(Result(scalars=[uuid4(), root.unit_id]))
    with pytest.raises(ValueError, match="topology revision"):
        repository.upsert_unit(child, child_revision)
