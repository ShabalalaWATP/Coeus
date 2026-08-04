from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.jioc_principals import (
    JIOC_AGENT_PRINCIPAL,
    PrincipalKind,
    principal_kind,
)
from coeus.domain.organisation import ManagementAction, OrganisationManagementGrant
from coeus.domain.organisation_authority import (
    OrganisationAuthorityDenied,
    OrganisationIdempotencyConflict,
)
from coeus.persistence.organisation_authority_postgres import (
    _load_command,
    _replay,
)
from coeus.persistence.organisation_authority_validation import (
    _require_current_principals,
    _row_covers,
    _row_effective,
    lock_lineages,
    transaction_time,
    validate_delegation,
    validate_lineage,
)

NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)


class _Result:
    def __init__(self, value: object = None, rows: tuple[dict[str, object], ...] = ()) -> None:
        self.value = value
        self.rows = rows

    def mappings(self) -> "_Result":
        return self

    def scalar_one(self) -> object:
        return self.value

    def first(self) -> object:
        return self.value

    def all(self) -> tuple[dict[str, object], ...]:
        return self.rows

    def __iter__(self) -> Iterator[dict[str, object]]:
        return iter(self.rows)


class _Connection:
    def __init__(self, result: _Result) -> None:
        self.result = result

    def execute(self, statement: object, params: object = None) -> _Result:
        return self.result


def _source(*, descendants: bool = True, valid_until: datetime | None = None) -> RowMapping:
    return cast(
        RowMapping,
        {
            "manager_user_id": uuid4(),
            "delegation_depth": 0,
            "include_descendants": descendants,
            "valid_until": valid_until,
        },
    )


def _grant(source: RowMapping) -> OrganisationManagementGrant:
    return OrganisationManagementGrant(
        uuid4(),
        uuid4(),
        uuid4(),
        ManagementAction.TASK_VIEW,
        False,
        NOW,
        UUID(str(source["manager_user_id"])),
        "Synthetic delegated grant",
        source_grant_id=uuid4(),
        delegation_depth=1,
    )


def test_delegation_validation_rejects_every_scope_expansion() -> None:
    source = _source()
    grant = _grant(source)
    validate_delegation(source, grant)
    with pytest.raises(OrganisationAuthorityDenied, match="creator"):
        validate_delegation(source, replace(grant, created_by_user_id=uuid4()))
    with pytest.raises(OrganisationAuthorityDenied, match="depth"):
        validate_delegation(source, replace(grant, delegation_depth=2))
    direct_source = cast(RowMapping, {**source, "include_descendants": False})
    with pytest.raises(OrganisationAuthorityDenied, match="scope"):
        validate_delegation(direct_source, replace(grant, include_descendants=True))
    expiring = cast(RowMapping, {**source, "valid_until": NOW + timedelta(days=1)})
    with pytest.raises(OrganisationAuthorityDenied, match="validity"):
        validate_delegation(expiring, grant)


def test_effectiveness_and_unit_coverage_are_fail_closed() -> None:
    root, child = uuid4(), uuid4()
    base = cast(
        RowMapping,
        {
            "root_unit_id": root,
            "include_descendants": False,
            "valid_from": NOW,
            "valid_until": None,
            "revoked_at": None,
        },
    )
    assert _row_effective(base, NOW)
    assert not _row_effective({**base, "valid_from": NOW + timedelta(seconds=1)}, NOW)  # type: ignore[arg-type]
    assert not _row_effective({**base, "valid_until": NOW}, NOW)  # type: ignore[arg-type]
    assert not _row_effective({**base, "revoked_at": NOW}, NOW)  # type: ignore[arg-type]
    connection = cast(Connection, _Connection(_Result((1,))))
    assert _row_covers(connection, base, root)
    assert not _row_covers(connection, base, child)
    descendant = cast(RowMapping, {**base, "include_descendants": True})
    assert _row_covers(connection, descendant, child)
    missing = cast(Connection, _Connection(_Result(None)))
    assert not _row_covers(missing, descendant, child)


def test_missing_lineage_and_invalid_database_clock_fail_closed() -> None:
    connection = cast(Connection, _Connection(_Result(rows=())))
    with pytest.raises(OrganisationAuthorityDenied, match="lineage is missing"):
        lock_lineages(connection, (uuid4(),))
    with pytest.raises(RuntimeError, match="transaction timestamp"):
        transaction_time(cast(Connection, _Connection(_Result("not-a-datetime"))))


def test_principal_classification_is_explicit_and_humans_require_active_accounts() -> None:
    human_id = uuid4()
    assert principal_kind(JIOC_AGENT_PRINCIPAL) is PrincipalKind.SERVICE
    assert principal_kind(human_id) is PrincipalKind.HUMAN
    rows = cast(
        tuple[RowMapping, ...],
        ({"manager_user_id": human_id, "created_by_user_id": human_id},),
    )
    active = cast(
        Connection,
        _Connection(_Result(rows=({"user_id": human_id, "is_active": True},))),
    )
    _require_current_principals(active, rows)
    for accounts in (
        (),
        ({"user_id": human_id, "is_active": False},),
    ):
        with pytest.raises(OrganisationAuthorityDenied, match="missing or suspended"):
            _require_current_principals(cast(Connection, _Connection(_Result(rows=accounts))), rows)


def test_registered_service_principal_does_not_depend_on_an_account_row() -> None:
    rows = cast(
        tuple[RowMapping, ...],
        (
            {
                "manager_user_id": JIOC_AGENT_PRINCIPAL,
                "created_by_user_id": JIOC_AGENT_PRINCIPAL,
            },
        ),
    )
    _require_current_principals(cast(Connection, _Connection(_Result(rows=()))), rows)


def test_distinct_human_grant_creator_must_also_be_active() -> None:
    holder_id, creator_id = uuid4(), uuid4()
    rows = cast(
        tuple[RowMapping, ...],
        ({"manager_user_id": holder_id, "created_by_user_id": creator_id},),
    )
    accounts = ({"user_id": holder_id, "is_active": True},)
    with pytest.raises(OrganisationAuthorityDenied, match="missing or suspended"):
        _require_current_principals(cast(Connection, _Connection(_Result(rows=accounts))), rows)


def _lineage_row() -> dict[str, object]:
    return {
        "grant_id": uuid4(),
        "manager_user_id": uuid4(),
        "root_unit_id": uuid4(),
        "action": ManagementAction.TASK_VIEW.value,
        "include_descendants": False,
        "valid_from": NOW,
        "valid_until": None,
        "revoked_at": None,
        "source_grant_id": None,
        "created_by_user_id": uuid4(),
        "delegation_depth": 0,
    }


def test_lineage_validation_rejects_missing_mismatched_and_inactive_rows() -> None:
    with pytest.raises(OrganisationAuthorityDenied, match="lineage is invalid"):
        validate_lineage(
            cast(Connection, _Connection(_Result(rows=()))),
            uuid4(),
            uuid4(),
            uuid4(),
            ManagementAction.TASK_VIEW,
            NOW,
        )
    row = _lineage_row()
    connection = cast(Connection, _Connection(_Result(rows=(row,))))
    with pytest.raises(OrganisationAuthorityDenied, match="actor or action"):
        validate_lineage(
            connection,
            UUID(str(row["grant_id"])),
            uuid4(),
            UUID(str(row["root_unit_id"])),
            ManagementAction.TASK_VIEW,
            NOW,
        )
    with pytest.raises(OrganisationAuthorityDenied, match="cover the target"):
        validate_lineage(
            connection,
            UUID(str(row["grant_id"])),
            UUID(str(row["manager_user_id"])),
            uuid4(),
            ManagementAction.TASK_VIEW,
            NOW,
        )
    inactive = {**row, "valid_from": NOW + timedelta(seconds=1)}
    with pytest.raises(OrganisationAuthorityDenied, match="not effective"):
        validate_lineage(
            cast(Connection, _Connection(_Result(rows=(inactive,)))),
            UUID(str(row["grant_id"])),
            UUID(str(row["manager_user_id"])),
            UUID(str(row["root_unit_id"])),
            ManagementAction.TASK_VIEW,
            NOW,
        )


def test_lineage_validation_rejects_invalid_root_and_delegation_link() -> None:
    root = _lineage_row()
    invalid_root = {**root, "source_grant_id": uuid4(), "delegation_depth": 1}
    with pytest.raises(OrganisationAuthorityDenied, match="valid root"):
        validate_lineage(
            cast(Connection, _Connection(_Result(rows=(invalid_root,)))),
            UUID(str(root["grant_id"])),
            UUID(str(root["manager_user_id"])),
            UUID(str(root["root_unit_id"])),
            ManagementAction.TASK_VIEW,
            NOW,
        )
    leaf = {
        **_lineage_row(),
        "manager_user_id": uuid4(),
        "source_grant_id": root["grant_id"],
        "delegation_depth": 1,
    }
    with pytest.raises(OrganisationAuthorityDenied, match="link is invalid"):
        validate_lineage(
            cast(Connection, _Connection(_Result(rows=(leaf, root)))),
            UUID(str(leaf["grant_id"])),
            UUID(str(leaf["manager_user_id"])),
            UUID(str(leaf["root_unit_id"])),
            ManagementAction.TASK_VIEW,
            NOW,
        )


def test_grant_command_row_collisions_and_replay_identity() -> None:
    command_id, actor_id, grant_id = uuid4(), uuid4(), uuid4()
    key, request_hash = "grant-command", "a" * 64
    row = {
        "command_id": command_id,
        "idempotency_key": key,
        "request_hash": request_hash,
        "command_type": "create",
        "actor_user_id": actor_id,
        "grant_id": grant_id,
        "result_version": 1,
    }
    connection = cast(Connection, _Connection(_Result(rows=(row, row))))
    with pytest.raises(OrganisationIdempotencyConflict, match="different rows"):
        _load_command(connection, command_id, key)
    assert _replay(None, command_id, key, request_hash, "create", actor_id, grant_id) is None
    assert _replay(
        cast(RowMapping, row), command_id, key, request_hash, "create", actor_id, grant_id
    ).replayed
    with pytest.raises(OrganisationIdempotencyConflict, match="another payload"):
        _replay(cast(RowMapping, row), command_id, key, "b" * 64, "create", actor_id, grant_id)
