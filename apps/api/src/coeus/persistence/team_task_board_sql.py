"""Bounded SQL for workflow-derived board detail and aggregate counts."""

# ruff: noqa: S608 - interpolated fragments are module constants, never input.

_COLUMN = """
CASE
 WHEN aggregate.state='ANALYST_ASSIGNMENT' THEN 'awaiting_analyst_assignment'
 WHEN aggregate.state='ANALYST_IN_PROGRESS' AND EXISTS(
   SELECT 1 FROM canonical_work_packages item
   WHERE item.ticket_id=ownership.ticket_id
     AND item.workflow_leg=ownership.workflow_leg
     AND item.state NOT IN ('complete','cancelled')
 ) AND NOT EXISTS(
   SELECT 1 FROM canonical_work_packages item
   WHERE item.ticket_id=ownership.ticket_id
     AND item.workflow_leg=ownership.workflow_leg
     AND item.state NOT IN ('blocked','complete','cancelled')
 ) THEN 'blocked'
 WHEN aggregate.state='ANALYST_IN_PROGRESS' AND EXISTS(
   SELECT 1 FROM canonical_work_packages item
   WHERE item.ticket_id=ownership.ticket_id
     AND item.workflow_leg=ownership.workflow_leg
 ) AND NOT EXISTS(
   SELECT 1 FROM canonical_work_packages item
   WHERE item.ticket_id=ownership.ticket_id
     AND item.workflow_leg=ownership.workflow_leg
     AND item.state IN ('in_progress','blocked','complete')
 ) THEN 'ready'
 WHEN aggregate.state='ANALYST_IN_PROGRESS' THEN 'in_progress'
 WHEN aggregate.state='MANAGER_APPROVAL' THEN 'manager_review'
 WHEN aggregate.state='QC_REVIEW' THEN 'qc_review'
 WHEN aggregate.state='REWORK_REQUIRED' THEN 'rework'
 WHEN aggregate.state='JIOC_INTERVENTION_HOLD' THEN 'on_hold'
 WHEN aggregate.state LIKE 'CLOSED_%' OR aggregate.state='CANCELLED'
   THEN 'completed_recently'
 ELSE 'unsupported'
END
"""

DETAIL = f"""
WITH projected AS (
 SELECT ownership.ticket_id,ownership.workflow_leg,ownership.target_date,
        ownership.owning_unit_id,unit.name unit_name,
        ownership.version ownership_version,aggregate.version ticket_version,
        aggregate.updated_at ticket_updated_at,aggregate.payload,
        {_COLUMN} board_column,
        COALESCE((SELECT jsonb_agg(jsonb_build_object(
          'package_id',package.package_id,'title',package.title,'state',package.state,
          'accountable_user_id',package.accountable_user_id,
          'estimated_minutes',package.estimated_minutes,
          'remaining_minutes',package.remaining_minutes,'due_at',package.due_at,
          'priority',package.priority,'version',package.version
        ) ORDER BY package.sort_order)
        FROM canonical_work_packages package
        WHERE package.ticket_id=ownership.ticket_id
          AND package.workflow_leg=ownership.workflow_leg
          AND package.state<>'cancelled'),'[]'::jsonb) packages
 FROM team_task_ownership ownership
 JOIN coeus_ticket_aggregates aggregate ON aggregate.ticket_id=ownership.ticket_id
 JOIN organisation_units unit ON unit.unit_id=ownership.owning_unit_id
 WHERE ownership.owning_unit_id=ANY(CAST(:unit_ids AS uuid[]))
   AND ownership.state NOT IN ('cancelled','ownership_unresolved')
)
SELECT * FROM projected
WHERE board_column<>'unsupported'
 AND (:include_completed OR board_column<>'completed_recently')
 AND (board_column<>'completed_recently' OR ticket_updated_at>=:completed_after)
 AND (CAST(:columns AS text[])='{{}}' OR board_column=ANY(CAST(:columns AS text[])))
 AND (CAST(:due_from AS date) IS NULL OR target_date>=CAST(:due_from AS date))
 AND (CAST(:due_to AS date) IS NULL OR target_date<=CAST(:due_to AS date))
 AND (CAST(:cursor_unit AS uuid) IS NULL OR
      (owning_unit_id,COALESCE(target_date,'9999-12-31'::date),ticket_id,workflow_leg) >
      (CAST(:cursor_unit AS uuid),COALESCE(CAST(:cursor_date AS date),'9999-12-31'::date),
       CAST(:cursor_ticket AS uuid),CAST(:cursor_leg AS text)))
ORDER BY owning_unit_id,COALESCE(target_date,'9999-12-31'::date),ticket_id,workflow_leg
LIMIT :candidate_limit
"""

AGGREGATES = f"""
WITH projected AS (
 SELECT ownership.owning_unit_id,unit.name unit_name,ownership.target_date,
        aggregate.updated_at ticket_updated_at,{_COLUMN} board_column
 FROM team_task_ownership ownership
 JOIN coeus_ticket_aggregates aggregate ON aggregate.ticket_id=ownership.ticket_id
 JOIN organisation_units unit ON unit.unit_id=ownership.owning_unit_id
 WHERE ownership.owning_unit_id=ANY(CAST(:unit_ids AS uuid[]))
   AND ownership.state NOT IN ('cancelled','ownership_unresolved')
)
SELECT owning_unit_id,unit_name,board_column,count(*) item_count FROM projected
WHERE board_column<>'unsupported'
 AND (:include_completed OR board_column<>'completed_recently')
 AND (board_column<>'completed_recently' OR ticket_updated_at>=:completed_after)
 AND (CAST(:columns AS text[])='{{}}' OR board_column=ANY(CAST(:columns AS text[])))
 AND (CAST(:due_from AS date) IS NULL OR target_date>=CAST(:due_from AS date))
 AND (CAST(:due_to AS date) IS NULL OR target_date<=CAST(:due_to AS date))
GROUP BY owning_unit_id,unit_name,board_column
ORDER BY owning_unit_id,board_column LIMIT 1000
"""
