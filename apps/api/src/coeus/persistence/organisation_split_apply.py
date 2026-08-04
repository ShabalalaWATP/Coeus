"""Transactional record mappings used by organisation split commands."""

from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.engine import Connection

from coeus.domain.organisation_merge import (
    MergeDisposition,
    MergeDispositionAction,
    MergeRecordKind,
)
from coeus.domain.organisation_split import OrganisationSplitCommand


def lock_split_records(connection: Connection, command: OrganisationSplitCommand) -> None:
    for kind, statement in _LOCK_RECORDS.items():
        identities = tuple(item for item in command.plan.dispositions if item.kind is kind)
        if identities:
            connection.execute(
                text(statement), {"ids": [str(item.record_id) for item in identities]}
            ).all()


def apply_split_dispositions(
    connection: Connection, command: OrganisationSplitCommand, occurred_at: datetime
) -> None:
    for disposition in sorted(
        command.plan.dispositions, key=lambda item: (item.kind.value, str(item.record_id))
    ):
        values = {
            "record_id": disposition.record_id,
            "expected_version": disposition.expected_version,
            "occurred_at": occurred_at,
            "actor_user_id": command.actor_user_id,
            "reason": command.plan.request.reason,
            "target_unit_id": disposition.target_unit_id,
            "replacement_id": disposition.replacement_id,
            "command_id": command.command_id,
        }
        _apply_one(connection, command, disposition, values)


def _apply_one(
    connection: Connection,
    command: OrganisationSplitCommand,
    disposition: MergeDisposition,
    values: dict[str, object],
) -> None:
    if disposition.kind is MergeRecordKind.CHILD_UNIT:
        _move_child(connection, command, disposition, values)
    elif disposition.kind is MergeRecordKind.MEMBERSHIP:
        _membership(connection, disposition, values)
    elif disposition.kind is MergeRecordKind.GRANT:
        _one(connection, _REVOKE_GRANT, values)
    elif disposition.kind is MergeRecordKind.DELIVERY_PROFILE:
        statement = (
            _MOVE_PROFILE if disposition.action is MergeDispositionAction.MOVE else _END_PROFILE
        )
        _one(connection, statement, values)
    elif disposition.kind is MergeRecordKind.CAPABILITY:
        statement = (
            _MOVE_CAPABILITY
            if disposition.action is MergeDispositionAction.MOVE
            else _END_CAPABILITY
        )
        _one(connection, statement, values)
    elif disposition.kind is MergeRecordKind.TASK:
        if disposition.action is MergeDispositionAction.MOVE:
            revision_id = connection.execute(
                text(_TARGET_REVISION), {"target_unit_id": disposition.target_unit_id}
            ).scalar_one()
            _one(connection, _MOVE_TASK, {**values, "target_revision_id": revision_id})
        else:
            _one(connection, _CANCEL_TASK, values)
    else:
        _one(connection, _CANCEL_TRANSFER, values)


def _membership(
    connection: Connection, disposition: MergeDisposition, values: dict[str, object]
) -> None:
    row = connection.execute(text(_END_MEMBERSHIP), values).mappings().one()
    if disposition.action is MergeDispositionAction.END:
        return
    connection.execute(text(_INSERT_MEMBERSHIP), {**values, **dict(row)}).scalar_one()


def _move_child(
    connection: Connection,
    command: OrganisationSplitCommand,
    disposition: MergeDisposition,
    values: dict[str, object],
) -> None:
    connection.execute(
        text("SELECT set_config('coeus.organisation_split_command',:command_id,true)"),
        {"command_id": str(command.command_id)},
    )
    _one(connection, _MOVE_CHILD, values)
    connection.execute(text(_DELETE_EXTERNAL_CLOSURE), values)
    connection.execute(text(_INSERT_EXTERNAL_CLOSURE), values)
    for row in connection.execute(text(_LOAD_CHILD_REVISION_PATHS), values).mappings():
        unit_id = UUID(str(row["unit_id"]))
        revision_id = uuid5(
            NAMESPACE_URL,
            f"coeus:organisation:split:revision:{command.command_id}:"
            f"{disposition.record_id}:{unit_id}",
        )
        connection.execute(
            text(_INSERT_TOPOLOGY_REVISION),
            {
                **values,
                "revision_id": revision_id,
                "revision_unit_id": unit_id,
                "revision_parent_unit_id": row["parent_unit_id"],
                "path": row["path"],
            },
        ).one()


def _one(connection: Connection, statement: str, values: dict[str, object]) -> None:
    connection.execute(text(statement), values).one()


_LOCK_RECORDS = {
    MergeRecordKind.CHILD_UNIT: "SELECT unit_id FROM organisation_units "
    "WHERE unit_id=ANY(CAST(:ids AS uuid[])) ORDER BY unit_id FOR UPDATE",
    MergeRecordKind.MEMBERSHIP: "SELECT membership_id FROM team_memberships "
    "WHERE membership_id=ANY(CAST(:ids AS uuid[])) ORDER BY membership_id FOR UPDATE",
    MergeRecordKind.GRANT: "SELECT grant_id FROM team_management_grants "
    "WHERE grant_id=ANY(CAST(:ids AS uuid[])) ORDER BY grant_id FOR UPDATE",
    MergeRecordKind.DELIVERY_PROFILE: "SELECT profile_id FROM team_delivery_profiles "
    "WHERE profile_id=ANY(CAST(:ids AS uuid[])) ORDER BY profile_id FOR UPDATE",
    MergeRecordKind.CAPABILITY: "SELECT coverage_id FROM team_capability_coverage "
    "WHERE coverage_id=ANY(CAST(:ids AS uuid[])) ORDER BY coverage_id FOR UPDATE",
    MergeRecordKind.TASK: "SELECT ownership_id FROM team_task_ownership "
    "WHERE ownership_id=ANY(CAST(:ids AS uuid[])) ORDER BY ownership_id FOR UPDATE",
    MergeRecordKind.PENDING_TRANSFER: "SELECT command_id FROM organisation_personnel_transfers "
    "WHERE command_id=ANY(CAST(:ids AS uuid[])) ORDER BY command_id FOR UPDATE",
}

_END_MEMBERSHIP = """
WITH original AS MATERIALIZED (
 SELECT user_id,role,assignment_eligible,valid_from,valid_until FROM team_memberships
 WHERE membership_id=:record_id AND version=:expected_version AND state='active'
  AND (valid_until IS NULL OR valid_until>:occurred_at)
), updated AS (
 UPDATE team_memberships SET
  state=CASE WHEN valid_from<=:occurred_at THEN 'ended' ELSE 'cancelled' END,
  assignment_eligible=false,
  valid_until=CASE WHEN valid_from<=:occurred_at THEN :occurred_at ELSE NULL END,
  version=version + 1,updated_at=:occurred_at
 WHERE membership_id=:record_id AND version=:expected_version
  AND EXISTS (SELECT 1 FROM original) RETURNING membership_id
)
SELECT original.user_id,original.role,original.assignment_eligible,
 CASE WHEN original.valid_from>:occurred_at THEN original.valid_from
      ELSE :occurred_at END replacement_valid_from,
 original.valid_until original_valid_until
FROM original CROSS JOIN updated
"""

_INSERT_MEMBERSHIP = """
INSERT INTO team_memberships(membership_id,user_id,unit_id,role,state,assignment_eligible,
 valid_from,valid_until,created_by_user_id,reason,provenance,version)
VALUES (:replacement_id,:user_id,:target_unit_id,:role,'active',:assignment_eligible,
 :replacement_valid_from,:original_valid_until,:actor_user_id,:reason,'organisation_split',1)
RETURNING version
"""

_REVOKE_GRANT = """
UPDATE team_management_grants SET revoked_at=GREATEST(:occurred_at,valid_from),
 revoked_by_user_id=:actor_user_id,
 revocation_reason=:reason,version=version + 1,updated_at=:occurred_at
WHERE grant_id=:record_id AND version=:expected_version AND revoked_at IS NULL
 AND (valid_until IS NULL OR valid_until>:occurred_at)
RETURNING version
"""

_MOVE_PROFILE = """
UPDATE team_delivery_profiles SET unit_id=:target_unit_id,policy_version=policy_version + 1,
 updated_at=:occurred_at WHERE profile_id=:record_id AND policy_version=:expected_version
 AND is_active RETURNING policy_version
"""

_END_PROFILE = """
UPDATE team_delivery_profiles SET is_active=false,policy_version=policy_version + 1,
 updated_at=:occurred_at WHERE profile_id=:record_id AND policy_version=:expected_version
 AND is_active RETURNING policy_version
"""

_MOVE_CAPABILITY = """
UPDATE team_capability_coverage SET policy_version=policy_version + 1
WHERE coverage_id=:record_id AND policy_version=:expected_version
 AND (valid_until IS NULL OR valid_until>:occurred_at) RETURNING policy_version
"""

_END_CAPABILITY = """
UPDATE team_capability_coverage SET
 valid_until=GREATEST(:occurred_at,valid_from + interval '1 microsecond'),
 policy_version=policy_version + 1
WHERE coverage_id=:record_id AND policy_version=:expected_version
 AND (valid_until IS NULL OR valid_until>:occurred_at)
RETURNING policy_version
"""

_TARGET_REVISION = """
SELECT revision_id FROM organisation_topology_revisions
WHERE unit_id=:target_unit_id ORDER BY valid_from DESC,revision_id DESC LIMIT 1
"""

_MOVE_TASK = """
UPDATE team_task_ownership SET owning_unit_id=:target_unit_id,
 topology_revision_id=:target_revision_id,version=version + 1,
 history_reference=:command_id,reason=:reason,updated_at=:occurred_at
WHERE ownership_id=:record_id AND version=:expected_version
 AND state NOT IN ('completed','cancelled') RETURNING version
"""

_CANCEL_TASK = """
UPDATE team_task_ownership SET state='cancelled',accepted_at=NULL,version=version + 1,
 history_reference=:command_id,reason=:reason,updated_at=:occurred_at
WHERE ownership_id=:record_id AND version=:expected_version
 AND state NOT IN ('completed','cancelled') RETURNING version
"""

_CANCEL_TRANSFER = """
UPDATE organisation_personnel_transfers SET status='cancelled',failure_code='organisation_split'
WHERE command_id=:record_id AND status='pending' RETURNING command_id
"""

_MOVE_CHILD = """
UPDATE organisation_units SET parent_unit_id=:target_unit_id,version=version + 1,
 updated_at=:occurred_at WHERE unit_id=:record_id AND version=:expected_version
 AND is_active RETURNING version
"""

_DELETE_EXTERNAL_CLOSURE = """
DELETE FROM organisation_unit_closure
WHERE descendant_unit_id IN (SELECT descendant_unit_id FROM organisation_unit_closure
 WHERE ancestor_unit_id=:record_id)
AND ancestor_unit_id NOT IN (SELECT descendant_unit_id FROM organisation_unit_closure
 WHERE ancestor_unit_id=:record_id)
"""

_INSERT_EXTERNAL_CLOSURE = """
INSERT INTO organisation_unit_closure(ancestor_unit_id,descendant_unit_id,depth)
SELECT parent_path.ancestor_unit_id,subtree.descendant_unit_id,
 parent_path.depth + 1 + subtree.depth
FROM organisation_unit_closure parent_path CROSS JOIN organisation_unit_closure subtree
WHERE parent_path.descendant_unit_id=:target_unit_id AND subtree.ancestor_unit_id=:record_id
"""

_LOAD_CHILD_REVISION_PATHS = """
SELECT unit_row.unit_id,unit_row.parent_unit_id,
 array_agg(closure.ancestor_unit_id ORDER BY closure.depth DESC) path
FROM organisation_units unit_row
JOIN organisation_unit_closure closure ON closure.descendant_unit_id=unit_row.unit_id
WHERE unit_row.unit_id IN (SELECT descendant_unit_id FROM organisation_unit_closure
 WHERE ancestor_unit_id=:record_id)
GROUP BY unit_row.unit_id,unit_row.parent_unit_id ORDER BY unit_row.unit_id
"""

_INSERT_TOPOLOGY_REVISION = """
INSERT INTO organisation_topology_revisions(revision_id,unit_id,parent_unit_id,path,
 valid_from,valid_until,change_command_id,changed_by_user_id)
VALUES (:revision_id,:revision_unit_id,:revision_parent_unit_id,:path,
 :occurred_at,NULL,:command_id,:actor_user_id) RETURNING revision_id
"""
