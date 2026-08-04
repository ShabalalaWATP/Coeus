"""SQL statements for canonical workforce calendar persistence."""

GET_EVENT = """
SELECT event.*, exceptions.exception_rows FROM calendar_events event
LEFT JOIN LATERAL (
  SELECT jsonb_agg(jsonb_build_object(
    'occurrence_key', occurrence_key, 'action', action, 'replacement', replacement
  ) ORDER BY occurrence_key) AS exception_rows
  FROM calendar_event_exceptions WHERE event_id=event.event_id
) exceptions ON TRUE
WHERE event.event_id=:event_id
"""

LOCK_EVENT = "SELECT * FROM calendar_events WHERE event_id=:event_id FOR UPDATE"

LIST_OWNER = """
SELECT event.*, exceptions.exception_rows
FROM calendar_events event
LEFT JOIN LATERAL (
  SELECT jsonb_agg(jsonb_build_object(
    'occurrence_key', occurrence_key, 'action', action, 'replacement', replacement
  ) ORDER BY occurrence_key) AS exception_rows
  FROM calendar_event_exceptions WHERE event_id=event.event_id
) exceptions ON TRUE
WHERE owner_user_id=:owner_user_id AND status <> 'cancelled'
AND (
    (starts_at IS NOT NULL AND starts_at < :window_end AND ends_at > :window_start)
    OR
    (all_day_start IS NOT NULL AND all_day_start < :window_end_date
        AND all_day_end > :window_start_date)
    OR (
      recurrence_rule IS NOT NULL
      AND COALESCE(starts_at, all_day_start::timestamp) < :window_end
      AND (recurrence_rule->>'until')::date >= :window_start_date
    )
)
ORDER BY COALESCE(starts_at, all_day_start::timestamp), event_id
LIMIT :limit
"""

LIST_UNIT_EVENTS = """
WITH projected AS (
  SELECT membership.unit_id AS projection_unit_id,event.event_id
  FROM team_memberships AS membership
  JOIN calendar_events AS event ON event.owner_user_id=membership.user_id
  WHERE membership.unit_id=ANY(CAST(:unit_ids AS uuid[]))
    AND membership.state='active'
    AND membership.valid_from<=:effective_at
    AND (membership.valid_until IS NULL OR :effective_at<membership.valid_until)
    AND event.source<>'team'
  UNION
  SELECT scope.unit_id AS projection_unit_id,event.event_id
  FROM calendar_event_scopes scope
  JOIN calendar_events event ON event.event_id=scope.event_id
  WHERE scope.scope_type='team_participant'
    AND scope.unit_id=ANY(CAST(:unit_ids AS uuid[]))
    AND event.source='team'
)
SELECT projected.projection_unit_id, event.*, exceptions.exception_rows
FROM projected
JOIN calendar_events AS event ON event.event_id=projected.event_id
LEFT JOIN LATERAL (
  SELECT jsonb_agg(jsonb_build_object(
    'occurrence_key', occurrence_key, 'action', action, 'replacement', replacement
  ) ORDER BY occurrence_key) AS exception_rows
  FROM calendar_event_exceptions WHERE event_id=event.event_id
) exceptions ON TRUE
WHERE EXISTS (
    SELECT 1 FROM organisation_unit_closure AS closure
    WHERE closure.ancestor_unit_id=:root_unit_id
      AND closure.descendant_unit_id=projected.projection_unit_id
  )
  AND event.status<>'cancelled'
  AND (
    (event.starts_at IS NOT NULL AND event.starts_at<:window_end
      AND event.ends_at>:window_start)
    OR
    (event.all_day_start IS NOT NULL AND event.all_day_start<:window_end_date
      AND event.all_day_end>:window_start_date)
    OR (
      event.recurrence_rule IS NOT NULL
      AND COALESCE(event.starts_at, event.all_day_start::timestamp)<:window_end
      AND (event.recurrence_rule->>'until')::date>=:window_start_date
    )
  )
ORDER BY COALESCE(event.starts_at, event.all_day_start::timestamp), event.event_id
LIMIT :limit
"""

COUNT_OVERLAPS = """
SELECT count(*) FROM calendar_events
WHERE owner_user_id=:owner_user_id AND event_id<>:event_id AND status='active'
AND (
    (CAST(:starts_at AS timestamptz) IS NOT NULL AND starts_at IS NOT NULL
        AND starts_at < CAST(:ends_at AS timestamptz)
        AND ends_at > CAST(:starts_at AS timestamptz))
    OR
    (CAST(:all_day_start AS date) IS NOT NULL AND all_day_start IS NOT NULL
        AND all_day_start < CAST(:all_day_end AS date)
        AND all_day_end > CAST(:all_day_start AS date))
)
"""

LOCK_HOME_MEMBERSHIP = """
SELECT membership_id,unit_id FROM team_memberships
WHERE user_id=:owner_user_id AND state='active'
  AND valid_from<=:occurred_at AND (valid_until IS NULL OR :occurred_at<valid_until)
ORDER BY membership_id FOR UPDATE
"""

LOAD_COMMAND = """
SELECT * FROM calendar_event_commands
WHERE command_id=:command_id
OR (actor_user_id=:actor_user_id AND idempotency_key=:idempotency_key)
ORDER BY command_id
"""

INSERT_EVENT = """
INSERT INTO calendar_events(
    event_id,owner_user_id,source,activity_category,starts_at,ends_at,
    all_day_start,all_day_end,time_zone,availability_effect,privacy_level,
    note,recurrence_rule,status,manager_scope_unit_id,created_by_user_id,
    created_at,updated_at,cancelled_at,version,provenance,deduplication_key
) VALUES (
    :event_id,:owner_user_id,:source,:activity_category,:starts_at,:ends_at,
    :all_day_start,:all_day_end,:time_zone,:availability_effect,:privacy_level,
    :note,CAST(:recurrence_rule AS jsonb),:status,:manager_scope_unit_id,
    :created_by_user_id,:occurred_at,:occurred_at,NULL,1,'canonical',:deduplication_key
) RETURNING version
"""

UPDATE_EVENT = """
UPDATE calendar_events SET
    activity_category=:activity_category,starts_at=:starts_at,ends_at=:ends_at,
    all_day_start=:all_day_start,all_day_end=:all_day_end,time_zone=:time_zone,
    availability_effect=:availability_effect,privacy_level=:privacy_level,
    note=:note,recurrence_rule=CAST(:recurrence_rule AS jsonb),
    deduplication_key=:deduplication_key,
    updated_at=:occurred_at,version=version+1
WHERE event_id=:event_id AND version=:expected_version AND status='active'
RETURNING version
"""

CANCEL_EVENT = """
UPDATE calendar_events SET status='cancelled',cancelled_at=:occurred_at,
updated_at=:occurred_at,version=version+1
WHERE event_id=:event_id AND version=:expected_version AND status='active'
RETURNING version
"""

INSERT_SCOPE = """
INSERT INTO calendar_event_scopes(
    scope_id,event_id,scope_type,subject_user_id,unit_id,created_at
) VALUES (:scope_id,:event_id,:scope_type,:owner_user_id,:unit_id,:occurred_at)
"""

INSERT_HISTORY = """
INSERT INTO calendar_event_versions(
    history_id,event_id,event_version,snapshot,changed_by_user_id,changed_at,
    change_reason_hash
) VALUES (
    :history_id,:event_id,:event_version,CAST(:snapshot AS jsonb),
    :actor_user_id,:occurred_at,:reason_hash
)
"""

INSERT_COMMAND = """
INSERT INTO calendar_event_commands(
    command_id,actor_user_id,idempotency_key,command_type,request_hash,
    event_id,result_version,future_event_id,created_at
) VALUES (
    :command_id,:actor_user_id,:idempotency_key,:command_type,:request_hash,
    :event_id,:result_version,:future_event_id,:occurred_at
) RETURNING command_id
"""

UPSERT_EXCEPTION = """
INSERT INTO calendar_event_exceptions(
  exception_id,event_id,occurrence_key,action,replacement,version,
  created_by_user_id,created_at
) VALUES (
  :exception_id,:event_id,:occurrence_key,:action,CAST(:replacement AS jsonb),1,
  :actor_user_id,:occurred_at
)
ON CONFLICT(event_id,occurrence_key) DO UPDATE SET
  action=EXCLUDED.action,replacement=EXCLUDED.replacement,
  version=calendar_event_exceptions.version+1,
  created_by_user_id=EXCLUDED.created_by_user_id,created_at=EXCLUDED.created_at
"""

BUMP_EVENT = """
UPDATE calendar_events SET updated_at=:occurred_at,version=version+1
WHERE event_id=:event_id AND version=:expected_version AND status='active'
RETURNING version
"""
