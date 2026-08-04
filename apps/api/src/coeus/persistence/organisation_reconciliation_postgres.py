"""Atomic PostgreSQL commit for one complete legacy organisation snapshot."""

import json
from dataclasses import replace
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from coeus.application.ports.organisation_reconciliation import (
    OrganisationReconciliationCommitter,
)
from coeus.domain.organisation import (
    OrganisationTopologyRevision,
    OrganisationUnit,
)
from coeus.domain.organisation_reconciliation import OrganisationReconciliationPlan
from coeus.persistence import organisation_postgres_sql as sql
from coeus.persistence.organisation_reconciliation_lifecycle import (
    deactivate_absent_teams as _deactivate_absent_teams,
)
from coeus.persistence.organisation_reconciliation_lifecycle import (
    end_absent_coverage as _end_absent_coverage,
)
from coeus.persistence.organisation_reconciliation_lifecycle import (
    next_version as _next_version,
)
from coeus.persistence.organisation_reconciliation_lifecycle import (
    resolve_membership_identities as _resolve_membership_identities,
)
from coeus.persistence.organisation_reconciliation_lifecycle import (
    versioned_upsert as _versioned_upsert,
)
from coeus.persistence.organisation_reconciliation_verification import projection_matches
from coeus.persistence.organisation_revision_query import insert_revision


class PostgresOrganisationReconciliation(OrganisationReconciliationCommitter):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def apply_reconciliation(self, plan: OrganisationReconciliationPlan) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:namespace, 0))"),
                {"namespace": plan.checkpoint.source_namespace},
            )
            plan = replace(
                plan,
                memberships=_resolve_membership_identities(
                    connection, plan.memberships, plan.effective_at
                ),
            )
            if _already_applied(connection, plan):
                return
            ended = _end_absent_memberships(connection, plan)
            _end_absent_coverage(connection, plan)
            _deactivate_absent_teams(connection, plan)
            for unit, revision in plan.units:
                _upsert_root_unit(connection, unit, revision)
            for profile in plan.delivery_profiles:
                _versioned_upsert(
                    connection,
                    sql.UPSERT_PROFILE,
                    profile,
                    "delivery profile",
                    "team_delivery_profiles",
                    "profile_id",
                    "policy_version",
                )
            for coverage in plan.capability_coverage:
                _versioned_upsert(
                    connection,
                    sql.UPSERT_COVERAGE,
                    coverage,
                    "capability coverage",
                    "team_capability_coverage",
                    "coverage_id",
                    "policy_version",
                )
            changed_memberships = {
                (membership.user_id, membership.unit_id)
                for membership in plan.memberships
                if _reconcile_membership(connection, membership)
            }
            _write_json_record(connection, sql.UPSERT_CHECKPOINT, plan.checkpoint, "cursor")
            for finding in plan.findings:
                _write_json_record(connection, sql.UPSERT_FINDING, finding, "details")
            affected = ended | changed_memberships
            _advance_epochs(connection, affected, plan)
            _append_evidence(connection, plan)


def _already_applied(connection: Connection, plan: OrganisationReconciliationPlan) -> bool:
    row = (
        connection.execute(
            text(
                "SELECT source_namespace, source_digest, status "
                "FROM organisation_reconciliation_checkpoints "
                "WHERE checkpoint_id = :checkpoint_id FOR UPDATE"
            ),
            {"checkpoint_id": plan.checkpoint.checkpoint_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return False
    if (
        row["source_namespace"] != plan.checkpoint.source_namespace
        or row["source_digest"] != plan.checkpoint.source_digest
    ):
        raise ValueError("reconciliation checkpoint identity is already in use")
    if str(row["status"]) != "completed":
        return False
    latest = (
        connection.execute(
            text(
                "SELECT checkpoint_id FROM organisation_reconciliation_checkpoints "
                "WHERE source_namespace=:source_namespace AND status='completed' "
                "ORDER BY completed_at DESC, updated_at DESC, checkpoint_id DESC LIMIT 1"
            ),
            {"source_namespace": plan.checkpoint.source_namespace},
        )
        .mappings()
        .first()
    )
    return (
        latest is not None
        and str(latest["checkpoint_id"]) == str(plan.checkpoint.checkpoint_id)
        and projection_matches(connection, plan)
    )


def _end_absent_memberships(
    connection: Connection, plan: OrganisationReconciliationPlan
) -> set[tuple[UUID, UUID]]:
    present = [item.membership_id for item in plan.memberships]
    invalid = connection.execute(
        text(
            "SELECT membership_id FROM team_memberships "
            "WHERE provenance = :provenance AND state IN ('active', 'suspended') "
            "AND NOT (membership_id = ANY(CAST(:present AS uuid[]))) "
            "AND valid_from >= :effective_at LIMIT 1"
        ),
        {
            "provenance": plan.checkpoint.source_namespace,
            "present": present,
            "effective_at": plan.effective_at,
        },
    ).first()
    if invalid is not None:
        raise ValueError("an absent membership cannot be ended before its start")
    rows = (
        connection.execute(
            text(
                "UPDATE team_memberships SET state = 'ended', assignment_eligible = false, "
                "valid_until = :effective_at, version = version + 1, updated_at = now() "
                "WHERE provenance = :provenance AND state IN ('active', 'suspended') "
                "AND NOT (membership_id = ANY(CAST(:present AS uuid[]))) "
                "RETURNING user_id, unit_id"
            ),
            {
                "provenance": plan.checkpoint.source_namespace,
                "present": present,
                "effective_at": plan.effective_at,
            },
        )
        .mappings()
        .all()
    )
    return {(UUID(str(row["user_id"])), UUID(str(row["unit_id"]))) for row in rows}


def _upsert_root_unit(
    connection: Connection,
    unit: OrganisationUnit,
    revision: OrganisationTopologyRevision,
) -> None:
    unit_params = _params(unit)
    if unit_params["parent_unit_id"] is not None:
        raise ValueError("legacy reconciliation accepts only flat root units")
    unit_params["version"] = _next_version(
        connection,
        "organisation_units",
        "unit_id",
        unit.unit_id,
        "version",
        unit_params,
    )
    if connection.execute(text(sql.UPSERT_UNIT), unit_params).first() is None:
        raise ValueError("unit identity cannot be changed by reconciliation")
    connection.execute(
        text(
            "INSERT INTO organisation_unit_closure(ancestor_unit_id, descendant_unit_id, depth) "
            "VALUES (:unit_id, :unit_id, 0) ON CONFLICT DO NOTHING"
        ),
        {"unit_id": unit_params["unit_id"]},
    )
    insert_revision(connection, revision)


def _required_upsert(connection: Connection, statement: str, value: object, label: str) -> None:
    if connection.execute(text(statement), _params(value)).first() is None:
        raise ValueError(f"{label} identity or version conflicts with stored state")


def _reconcile_membership(connection: Connection, membership: object) -> bool:
    params = _params(membership)
    existing = (
        connection.execute(
            text(
                "SELECT user_id, unit_id, role, state, assignment_eligible, valid_from, "
                "valid_until, created_by_user_id, reason, provenance, version "
                "FROM team_memberships "
                "WHERE membership_id = :membership_id FOR UPDATE"
            ),
            {"membership_id": params["membership_id"]},
        )
        .mappings()
        .first()
    )
    changed = existing is None
    if existing is not None:
        if existing["state"] in {"ended", "cancelled"}:
            raise ValueError("an ended membership requires an explicit new posting")
        if str(existing["user_id"]) != str(params["user_id"]) or str(existing["unit_id"]) != str(
            params["unit_id"]
        ):
            raise ValueError("membership identity is already in use")
        params["valid_from"] = existing["valid_from"]
        material_fields = (
            "role",
            "state",
            "assignment_eligible",
            "valid_from",
            "valid_until",
            "created_by_user_id",
            "reason",
            "provenance",
        )
        changed = any(str(existing[field]) != str(params[field]) for field in material_fields)
        current_version = int(str(existing["version"]))
        params["version"] = current_version + 1 if changed else current_version
    if connection.execute(text(sql.UPSERT_MEMBERSHIP), params).first() is None:
        raise ValueError("membership conflicts with stored authority state")
    return changed


def _write_json_record(
    connection: Connection, statement: str, value: object, json_field: str
) -> None:
    params = _params(value)
    params[json_field] = json.dumps(params[json_field], sort_keys=True)
    _required_upsert(connection, statement, _ParameterObject(params), value.__class__.__name__)


class _ParameterObject:
    def __init__(self, values: dict[str, object]) -> None:
        self.__dict__.update(values)


def _advance_epochs(
    connection: Connection,
    affected: set[tuple[UUID, UUID]],
    plan: OrganisationReconciliationPlan,
) -> None:
    for principal_id, scope_unit_id in sorted(
        affected, key=lambda item: (str(item[0]), str(item[1]))
    ):
        connection.execute(
            text(
                "INSERT INTO effective_authority_epochs"
                "(principal_id, scope_unit_id, epoch, advanced_at) "
                "VALUES (:principal_id, :scope_unit_id, 1, :advanced_at) "
                "ON CONFLICT (principal_id, scope_unit_id) DO UPDATE SET "
                "epoch = effective_authority_epochs.epoch + 1, "
                "advanced_at = EXCLUDED.advanced_at"
            ),
            {
                "principal_id": principal_id,
                "scope_unit_id": scope_unit_id,
                "advanced_at": plan.effective_at,
            },
        )


def _append_evidence(connection: Connection, plan: OrganisationReconciliationPlan) -> None:
    payload = {
        "source_digest": plan.checkpoint.source_digest,
        "units": len(plan.units),
        "memberships": len(plan.memberships),
        "blocking_findings": len(plan.findings),
    }
    event_id = uuid4()
    connection.execute(
        text(
            "INSERT INTO coeus_audit_events"
            "(event_id, event_type, occurred_at, actor_user_id, metadata) "
            "VALUES (:event_id, 'organisation_reconciled', :occurred_at, :actor, "
            "CAST(:payload AS jsonb)) ON CONFLICT (event_id) DO NOTHING"
        ),
        {
            "event_id": event_id,
            "occurred_at": plan.effective_at,
            "actor": str(plan.actor_user_id),
            "payload": json.dumps(payload, sort_keys=True),
        },
    )
    outbox_id = uuid4()
    connection.execute(
        text(
            "INSERT INTO coeus_outbox"
            "(event_id, aggregate_id, aggregate_version, event_type, payload) "
            "VALUES (:event_id, :aggregate_id, 1, 'organisation_reconciled', "
            "CAST(:payload AS jsonb)) "
            "ON CONFLICT (aggregate_id, aggregate_version, event_type) DO NOTHING"
        ),
        {
            "event_id": outbox_id,
            "aggregate_id": event_id,
            "payload": json.dumps(payload, sort_keys=True),
        },
    )


def _params(value: object) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, item in vars(value).items():
        output[key] = item.value if isinstance(item, StrEnum) else item
    return output
