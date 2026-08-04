"""PostgreSQL shadow repository for the inactive organisation foundation."""

import json
from datetime import datetime
from enum import StrEnum
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine, RowMapping

from coeus.application.ports.organisation import OrganisationRepository
from coeus.domain.organisation import (
    EffectiveAuthorityEpoch,
    MembershipRole,
    MembershipState,
    OrganisationManagementGrant,
    OrganisationReconciliationCheckpoint,
    OrganisationReconciliationFinding,
    OrganisationTopologyRevision,
    OrganisationUnit,
    TeamCapabilityCoverage,
    TeamDeliveryProfile,
    TeamMembership,
)
from coeus.persistence import organisation_postgres_sql as sql
from coeus.persistence.organisation_grant_query import (
    list_management_grants as query_management_grants,
)
from coeus.persistence.organisation_grant_rows import (
    decode_grant as _grant,
)
from coeus.persistence.organisation_grant_rows import (
    get_grant,
    unit_is_within,
)
from coeus.persistence.organisation_revision_query import insert_revision
from coeus.persistence.organisation_rows import decode_unit


class PostgresOrganisationRepository(OrganisationRepository):
    """Explicitly unwired repository used only by migration and shadow tooling."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_unit(self, unit_id: UUID) -> OrganisationUnit | None:
        with self._engine.begin() as connection:
            row = (
                connection.execute(
                    text("SELECT * FROM organisation_units WHERE unit_id = :unit_id"),
                    {"unit_id": unit_id},
                )
                .mappings()
                .first()
            )
        return None if row is None else decode_unit(row)

    def list_roots(self, *, limit: int = 100) -> tuple[OrganisationUnit, ...]:
        return self._units(
            "SELECT * FROM organisation_units WHERE parent_unit_id IS NULL "
            "ORDER BY name, unit_id LIMIT :limit",
            {"limit": _limit(limit, 100)},
        )

    def list_children(self, unit_id: UUID, *, limit: int = 100) -> tuple[OrganisationUnit, ...]:
        return self._units(
            "SELECT * FROM organisation_units WHERE parent_unit_id = :unit_id "
            "ORDER BY name, unit_id LIMIT :limit",
            {"unit_id": unit_id, "limit": _limit(limit, 100)},
        )

    def list_ancestors(
        self, unit_id: UUID, *, maximum_depth: int = 12
    ) -> tuple[OrganisationUnit, ...]:
        return self._units(
            "SELECT unit.* FROM organisation_unit_closure closure "
            "JOIN organisation_units unit ON unit.unit_id = closure.ancestor_unit_id "
            "WHERE closure.descendant_unit_id = :unit_id AND closure.depth BETWEEN 1 AND :depth "
            "ORDER BY closure.depth DESC",
            {"unit_id": unit_id, "depth": _depth(maximum_depth)},
        )

    def list_descendants(
        self, unit_id: UUID, *, maximum_depth: int = 12, limit: int = 1_000
    ) -> tuple[OrganisationUnit, ...]:
        return self._units(
            "SELECT unit.* FROM organisation_unit_closure closure "
            "JOIN organisation_units unit ON unit.unit_id = closure.descendant_unit_id "
            "WHERE closure.ancestor_unit_id = :unit_id AND closure.depth BETWEEN 1 AND :depth "
            "ORDER BY closure.depth, unit.name, unit.unit_id LIMIT :limit",
            {
                "unit_id": unit_id,
                "depth": _depth(maximum_depth),
                "limit": _limit(limit, 1_000),
            },
        )

    def list_memberships(self, user_id: UUID) -> tuple[TeamMembership, ...]:
        with self._engine.begin() as connection:
            rows = connection.execute(
                text(
                    "SELECT * FROM team_memberships WHERE user_id = :user_id "
                    "ORDER BY valid_from, membership_id"
                ),
                {"user_id": user_id},
            ).mappings()
            return tuple(_membership(row) for row in rows)

    def list_unit_memberships(
        self, unit_id: UUID, *, include_inactive: bool = False, limit: int = 200
    ) -> tuple[TeamMembership, ...]:
        with self._engine.begin() as connection:
            rows = connection.execute(
                text(
                    "SELECT * FROM team_memberships WHERE unit_id = :unit_id "
                    "AND (:include_inactive OR (state = 'active' "
                    "AND valid_from <= transaction_timestamp() "
                    "AND (valid_until IS NULL OR valid_until > transaction_timestamp()))) "
                    "ORDER BY state, role, valid_from, membership_id LIMIT :limit"
                ),
                {
                    "unit_id": unit_id,
                    "include_inactive": include_inactive,
                    "limit": _limit(limit, 500),
                },
            ).mappings()
            return tuple(_membership(row) for row in rows)

    def effective_membership(self, user_id: UUID, effective_at: datetime) -> TeamMembership | None:
        with self._engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT * FROM team_memberships WHERE user_id = :user_id "
                        "AND state <> 'cancelled' AND valid_from <= :effective_at "
                        "AND (valid_until IS NULL OR :effective_at < valid_until) "
                        "ORDER BY valid_from DESC LIMIT 1"
                    ),
                    {"user_id": user_id, "effective_at": effective_at},
                )
                .mappings()
                .first()
            )
        return None if row is None else _membership(row)

    def effective_grants(
        self, manager_user_id: UUID, effective_at: datetime
    ) -> tuple[OrganisationManagementGrant, ...]:
        with self._engine.begin() as connection:
            rows = connection.execute(
                text(
                    "SELECT * FROM team_management_grants "
                    "WHERE manager_user_id = :manager_user_id AND valid_from <= :effective_at "
                    "AND (valid_until IS NULL OR :effective_at < valid_until) "
                    "AND (revoked_at IS NULL OR :effective_at < revoked_at) "
                    "ORDER BY root_unit_id, action, grant_id"
                ),
                {"manager_user_id": manager_user_id, "effective_at": effective_at},
            ).mappings()
            return tuple(_grant(row) for row in rows)

    def get_management_grant(self, grant_id: UUID) -> OrganisationManagementGrant | None:
        return get_grant(self._engine, grant_id)

    def list_management_grants(
        self,
        *,
        root_unit_id: UUID | None = None,
        manager_user_id: UUID | None = None,
        include_inactive: bool = False,
        limit: int = 100,
    ) -> tuple[OrganisationManagementGrant, ...]:
        return query_management_grants(
            self._engine,
            root_unit_id=root_unit_id,
            manager_user_id=manager_user_id,
            include_inactive=include_inactive,
            limit=limit,
        )

    def unit_is_within(self, root_unit_id: UUID, target_unit_id: UUID) -> bool:
        return unit_is_within(self._engine, root_unit_id, target_unit_id)

    def upsert_unit(self, unit: OrganisationUnit, revision: OrganisationTopologyRevision) -> None:
        if revision.unit_id != unit.unit_id or revision.parent_unit_id != unit.parent_unit_id:
            raise ValueError("unit and topology revision identities must agree")
        with self._engine.begin() as connection:
            parent_path: tuple[UUID, ...] = ()
            if unit.parent_unit_id is not None:
                parent_path = tuple(
                    UUID(str(value))
                    for value in connection.execute(
                        text(
                            "SELECT ancestor_unit_id FROM organisation_unit_closure "
                            "WHERE descendant_unit_id = :parent_unit_id ORDER BY depth DESC"
                        ),
                        {"parent_unit_id": unit.parent_unit_id},
                    ).scalars()
                )
                if not parent_path:
                    raise ValueError("parent closure path is missing")
            if revision.path != (*parent_path, unit.unit_id):
                raise ValueError("topology revision does not match the current parent path")
            existing = (
                connection.execute(
                    text("SELECT parent_unit_id FROM organisation_units WHERE unit_id = :unit_id"),
                    {"unit_id": unit.unit_id},
                )
                .mappings()
                .first()
            )
            existing_parent = None if existing is None else existing["parent_unit_id"]
            if existing is not None and _uuid(existing_parent) != unit.parent_unit_id:
                raise ValueError("shadow upsert cannot reparent an existing unit")
            if connection.execute(text(sql.UPSERT_UNIT), _params(unit)).first() is None:
                raise ValueError("unit identity cannot be changed by shadow reconciliation")
            connection.execute(
                text(
                    "INSERT INTO organisation_unit_closure"
                    "(ancestor_unit_id, descendant_unit_id, depth) "
                    "VALUES (:unit_id, :unit_id, 0) ON CONFLICT DO NOTHING"
                ),
                {"unit_id": unit.unit_id},
            )
            if unit.parent_unit_id is not None:
                connection.execute(
                    text(
                        "INSERT INTO organisation_unit_closure"
                        "(ancestor_unit_id, descendant_unit_id, depth) "
                        "SELECT ancestor_unit_id, :unit_id, depth + 1 "
                        "FROM organisation_unit_closure WHERE descendant_unit_id = :parent_unit_id "
                        "AND depth < 12 ON CONFLICT DO NOTHING RETURNING ancestor_unit_id"
                    ),
                    {"unit_id": unit.unit_id, "parent_unit_id": unit.parent_unit_id},
                )
                direct_path = connection.execute(
                    text(
                        "SELECT 1 FROM organisation_unit_closure WHERE ancestor_unit_id = "
                        ":parent_unit_id AND descendant_unit_id = :unit_id AND depth = 1"
                    ),
                    {"unit_id": unit.unit_id, "parent_unit_id": unit.parent_unit_id},
                ).first()
                if direct_path is None:
                    raise ValueError("parent closure path is missing or exceeds maximum depth")
            insert_revision(connection, revision)

    def upsert_membership(self, membership: TeamMembership) -> None:
        self._upsert(sql.UPSERT_MEMBERSHIP, membership, "membership")

    def upsert_management_grant(self, grant: OrganisationManagementGrant) -> None:
        self._upsert(sql.UPSERT_GRANT, grant, "management grant")

    def upsert_delivery_profile(self, profile: TeamDeliveryProfile) -> None:
        self._upsert(sql.UPSERT_PROFILE, profile, "delivery profile")

    def upsert_capability_coverage(self, coverage: TeamCapabilityCoverage) -> None:
        self._upsert(sql.UPSERT_COVERAGE, coverage, "capability coverage")

    def upsert_authority_epoch(self, epoch: EffectiveAuthorityEpoch) -> None:
        self._upsert(sql.UPSERT_EPOCH, epoch, "authority epoch")

    def upsert_checkpoint(self, checkpoint: OrganisationReconciliationCheckpoint) -> None:
        params = _params(checkpoint)
        params["cursor"] = json.dumps(checkpoint.cursor, sort_keys=True)
        if not self._execute(sql.UPSERT_CHECKPOINT, params):
            raise ValueError("checkpoint identity cannot be changed by shadow reconciliation")

    def upsert_finding(self, finding: OrganisationReconciliationFinding) -> None:
        params = _params(finding)
        params["details"] = json.dumps(finding.details, sort_keys=True)
        if not self._execute(sql.UPSERT_FINDING, params):
            raise ValueError("finding identity cannot be changed by shadow reconciliation")

    def _units(self, statement: str, params: dict[str, object]) -> tuple[OrganisationUnit, ...]:
        with self._engine.begin() as connection:
            rows = connection.execute(text(statement), params).mappings()
            return tuple(decode_unit(row) for row in rows)

    def _upsert(self, statement: str, value: object, label: str) -> None:
        if not self._execute(statement, _params(value)):
            raise ValueError(f"{label} identity cannot be changed by shadow reconciliation")

    def _execute(self, statement: str, params: dict[str, object]) -> bool:
        with self._engine.begin() as connection:
            return connection.execute(text(statement), params).first() is not None


def _params(value: object) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, item in vars(value).items():
        if isinstance(item, StrEnum):
            output[key] = item.value
        elif isinstance(item, tuple) and all(isinstance(part, UUID) for part in item):
            output[key] = list(item)
        else:
            output[key] = item
    return output


def _membership(row: RowMapping) -> TeamMembership:
    return TeamMembership(
        UUID(str(row["membership_id"])),
        UUID(str(row["user_id"])),
        UUID(str(row["unit_id"])),
        MembershipRole(str(row["role"])),
        MembershipState(str(row["state"])),
        bool(row["assignment_eligible"]),
        cast(datetime, row["valid_from"]),
        UUID(str(row["created_by_user_id"])),
        str(row["reason"]),
        str(row["provenance"]),
        cast(datetime | None, row["valid_until"]),
        int(str(row["version"])),
    )


def _depth(value: int) -> int:
    if not 0 <= value <= 12:
        raise ValueError("maximum_depth must be between zero and 12")
    return value


def _uuid(value: object) -> UUID | None:
    return None if value is None else UUID(str(value))


def _limit(value: int, maximum: int) -> int:
    if not 1 <= value <= maximum:
        raise ValueError(f"limit must be between one and {maximum}")
    return value
