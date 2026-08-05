"""SQL statements for conserved personal-capacity reservations."""

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
PACKAGE = """
SELECT * FROM canonical_work_packages
WHERE package_id=:package_id AND state IN ('ready','in_progress','blocked') FOR UPDATE
"""
AUTHORITY_PACKAGE = """
SELECT owning_unit_id FROM canonical_work_packages WHERE package_id=:package_id
"""
MEMBERSHIP = """
SELECT unit_id,assignment_eligible FROM team_memberships
WHERE user_id=:user_id AND state='active' AND valid_from<=:start
  AND (valid_until IS NULL OR :end<=valid_until) FOR UPDATE
"""
GRANTS = """
SELECT grant_id,root_unit_id FROM team_management_grants
WHERE manager_user_id=:actor_id AND action='task:assign'
  AND (
    root_unit_id=:unit_id OR (
      include_descendants AND EXISTS(
        SELECT 1 FROM organisation_unit_closure
        WHERE ancestor_unit_id=root_unit_id AND descendant_unit_id=:unit_id
      )
    )
  )
  AND valid_from<=:at AND (valid_until IS NULL OR :at<valid_until)
  AND (revoked_at IS NULL OR :at<revoked_at)
ORDER BY grant_id LIMIT 20
"""
PATTERN = """
SELECT * FROM working_patterns
WHERE user_id=:user_id AND valid_from<=:start AND (valid_until IS NULL OR :end<=valid_until)
FOR UPDATE
"""
CALENDAR = """
SELECT event.starts_at,event.ends_at,event.all_day_start,event.all_day_end,
       event.time_zone,event.recurrence_rule,event.availability_effect,
       exceptions.exception_rows
FROM calendar_events event
LEFT JOIN LATERAL (
  SELECT jsonb_agg(jsonb_build_object(
    'occurrence_key',occurrence_key,'action',action,'replacement',replacement
  ) ORDER BY occurrence_key) AS exception_rows
  FROM calendar_event_exceptions WHERE event_id=event.event_id
) exceptions ON TRUE
WHERE event.owner_user_id=:user_id AND event.status='active'
  AND (
    availability_effect IN ('partial','unavailable')
    OR EXISTS (
      SELECT 1 FROM calendar_event_exceptions blocking
      WHERE blocking.event_id=event.event_id AND blocking.action='change'
        AND blocking.replacement->>'availability' IN ('partial','unavailable')
    )
  )
  AND (
    (starts_at<:end AND ends_at>:start) OR recurrence_rule IS NOT NULL OR
    (
      all_day_start < (timezone(time_zone,:end)::date + 1)
      AND all_day_end > timezone(time_zone,:start)::date
    )
  )
FOR UPDATE OF event
LIMIT 501
"""
RESERVED = """
SELECT coalesce(sum(reserved_minutes),0) FROM capacity_reservations
WHERE user_id=:user_id AND state IN ('held','active') AND starts_at<:end AND ends_at>:start
"""
EXCEPTIONS = """
SELECT reduction_minutes,reduction_percent FROM capacity_exceptions
WHERE user_id=:user_id AND starts_at<:end AND ends_at>:start FOR UPDATE
"""
INSERT = """
INSERT INTO capacity_reservations(
 reservation_id,user_id,ticket_id,workflow_leg,package_id,starts_at,ends_at,reserved_minutes,
 state,expires_at,idempotency_key,request_hash,actor_user_id,version,created_at,updated_at,
 participant_role)
VALUES (
 :reservation_id,:user_id,:ticket_id,:workflow_leg,:package_id,:starts_at,:ends_at,:minutes,
 'active',NULL,:key,:request_hash,:actor_id,1,:now,:now,:participant_role)
RETURNING *
"""
