"""SQL for reviewed dependency commands."""

PACKAGE = """
SELECT package.*,ownership.version ownership_version,
       ownership.state ownership_state,ownership.owning_unit_id ownership_unit_id
FROM canonical_work_packages package
JOIN team_task_ownership ownership
  ON ownership.ticket_id=package.ticket_id AND ownership.workflow_leg=package.workflow_leg
WHERE package.package_id IN (:package_id,:predecessor_id)
ORDER BY package.package_id
"""
PACKAGE_FOR_UPDATE = PACKAGE + " FOR UPDATE OF package,ownership"

GRAPH_PACKAGES = """
SELECT package_id FROM canonical_work_packages
WHERE ticket_id=:ticket_id AND workflow_leg=:workflow_leg ORDER BY package_id LIMIT 129
"""
GRAPH_PACKAGES_FOR_UPDATE = GRAPH_PACKAGES + " FOR UPDATE"

GRAPH_EDGES = """
SELECT dependency.package_id,dependency.predecessor_package_id
FROM work_package_dependencies dependency
JOIN canonical_work_packages package ON package.package_id=dependency.package_id
WHERE package.ticket_id=:ticket_id AND package.workflow_leg=:workflow_leg
ORDER BY dependency.package_id,dependency.predecessor_package_id LIMIT 513
"""
GRAPH_EDGES_FOR_UPDATE = GRAPH_EDGES + " FOR UPDATE OF dependency"

LEAF_UNIT = """
SELECT unit.unit_id FROM organisation_units unit
WHERE unit.unit_id=:unit_id AND unit.is_active
  AND unit.valid_from<=:at AND (unit.valid_until IS NULL OR :at<unit.valid_until)
  AND NOT EXISTS (SELECT 1 FROM organisation_units child
    WHERE child.parent_unit_id=unit.unit_id AND child.is_active
      AND child.valid_from<=:at AND (child.valid_until IS NULL OR :at<child.valid_until))
FOR UPDATE
"""

GRANT = """
SELECT grant_id,version FROM team_management_grants
WHERE grant_id=:grant_id AND manager_user_id=:actor_id AND action='task:assign'
  AND valid_from<=:at AND (valid_until IS NULL OR :at<valid_until)
  AND (revoked_at IS NULL OR :at<revoked_at)
  AND (root_unit_id=:unit_id OR (include_descendants AND EXISTS(
    SELECT 1 FROM organisation_unit_closure
    WHERE ancestor_unit_id=root_unit_id AND descendant_unit_id=:unit_id)))
FOR UPDATE
"""

DEPENDENCY = """
SELECT 1 FROM work_package_dependencies
WHERE package_id=:package_id AND predecessor_package_id=:predecessor_id
"""

COMMANDS = """
SELECT * FROM work_package_dependency_commands
WHERE command_id=:command_id OR idempotency_key=:idempotency_key
ORDER BY command_id FOR UPDATE
"""

UPDATE_PACKAGE = """
UPDATE canonical_work_packages SET version=version+1,updated_at=:at
WHERE package_id=:package_id AND version=:expected_version RETURNING version
"""

ADD_DEPENDENCY = """
INSERT INTO work_package_dependencies
(package_id,predecessor_package_id,created_by_user_id,created_at)
VALUES (:package_id,:predecessor_id,:actor_id,:at)
"""

REMOVE_DEPENDENCY = """
DELETE FROM work_package_dependencies
WHERE package_id=:package_id AND predecessor_package_id=:predecessor_id
"""

INSERT_COMMAND = """
INSERT INTO work_package_dependency_commands(
 command_id,idempotency_key,request_hash,package_id,predecessor_package_id,actor_user_id,
 operation,expected_package_version,expected_predecessor_version,expected_ownership_version,
 expected_grant_version,result_package_version,result_active,occurred_at)
VALUES (:command_id,:idempotency_key,:request_hash,:package_id,:predecessor_id,:actor_id,
 :operation,:expected_package_version,:expected_predecessor_version,:expected_ownership_version,
 :expected_grant_version,:result_package_version,:result_active,:at)
"""

INSERT_HISTORY = """
INSERT INTO work_package_history(
 history_id,package_id,version,actor_user_id,event_type,evidence,occurred_at)
VALUES (:history_id,:package_id,:version,:actor_id,:event_type,CAST(:evidence AS jsonb),:at)
"""
