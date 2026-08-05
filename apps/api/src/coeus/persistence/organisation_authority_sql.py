"""SQL statements for transactional organisation grant commands."""

LOAD_COMMAND = """
SELECT command_id, idempotency_key, request_hash, command_type, actor_user_id,
 grant_id, result_version FROM organisation_grant_commands
WHERE idempotency_key = :idempotency_key OR command_id = :command_id
FOR UPDATE
"""

LINEAGE = """
WITH RECURSIVE lineage AS (
 SELECT item.*, 0 AS chain_depth FROM team_management_grants item
 WHERE item.grant_id = :grant_id
 UNION ALL
 SELECT source.*, lineage.chain_depth + 1 FROM team_management_grants source
 JOIN lineage ON source.grant_id = lineage.source_grant_id
 WHERE lineage.chain_depth < 3
)
SELECT * FROM lineage ORDER BY chain_depth
"""

INSERT_GRANT = """
INSERT INTO team_management_grants(
 grant_id, manager_user_id, root_unit_id, action, include_descendants,
 valid_from, valid_until, revoked_at, created_by_user_id, reason,
 source_grant_id, delegation_depth, version, revoked_by_user_id, revocation_reason
) VALUES (
 :grant_id, :manager_user_id, :root_unit_id, :action, :include_descendants,
 :valid_from, :valid_until, :revoked_at, :created_by_user_id, :reason,
 :source_grant_id, :delegation_depth, :version, :revoked_by_user_id, :revocation_reason
)
RETURNING grant_id, version
"""

REVOKE_GRANT = """
UPDATE team_management_grants SET revoked_at = :occurred_at,
 revoked_by_user_id = :actor_user_id, revocation_reason = :reason,
 version = version + 1, updated_at = now()
WHERE grant_id = :grant_id AND version = :expected_version AND revoked_at IS NULL
RETURNING version
"""

INSERT_COMMAND = """
INSERT INTO organisation_grant_commands(
 command_id, idempotency_key, request_hash, command_type, actor_user_id,
 grant_id, authorising_grant_id, result_version, created_at
) VALUES (
 :command_id, :idempotency_key, :request_hash, :command_type, :actor_user_id,
 :grant_id, :authorising_grant_id, :result_version, :occurred_at
)
RETURNING result_version
"""

AFFECTED_GRANTS = """
WITH RECURSIVE affected AS (
 SELECT grant_id, manager_user_id, root_unit_id FROM team_management_grants
 WHERE grant_id = :grant_id
 UNION
 SELECT child.grant_id, child.manager_user_id, child.root_unit_id
 FROM team_management_grants child
 JOIN affected source ON child.source_grant_id = source.grant_id
)
SELECT grant_id, manager_user_id, root_unit_id FROM affected ORDER BY grant_id
"""

ADVANCE_EPOCH = """
INSERT INTO effective_authority_epochs(principal_id, scope_unit_id, epoch, advanced_at)
VALUES (:principal_id, :scope_unit_id, 1, :occurred_at)
ON CONFLICT (principal_id, scope_unit_id) DO UPDATE SET
 epoch = effective_authority_epochs.epoch + 1, advanced_at = EXCLUDED.advanced_at
"""

INSERT_AUDIT = """
INSERT INTO coeus_audit_events(event_id, event_type, occurred_at, actor_user_id, metadata)
VALUES (:event_id, :event_type, :occurred_at, :actor_user_id, CAST(:payload AS jsonb))
ON CONFLICT (event_id) DO NOTHING
"""

INSERT_OUTBOX = """
INSERT INTO coeus_outbox(event_id, aggregate_id, aggregate_version, event_type, payload)
VALUES (:event_id, :grant_id, :version, :event_type, CAST(:payload AS jsonb))
ON CONFLICT (aggregate_id, aggregate_version, event_type) DO NOTHING
"""
