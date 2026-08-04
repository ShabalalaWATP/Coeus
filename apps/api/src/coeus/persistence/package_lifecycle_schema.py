"""Schema and database invariants for package lifecycle reconciliation."""

from collections.abc import Sequence


def package_lifecycle_schema_statements() -> Sequence[str]:
    return (
        _RESERVATION_ROLE,
        _CONFLICTS,
        _DISPOSITION_COMMANDS,
        _IMMUTABLE,
        _PREDECESSOR_GUARD,
        _TERMINAL_RECONCILIATION,
        _PERSON_RECONCILIATION,
        _TICKET_RECONCILIATION,
        _INPUT_CONFLICTS,
        _TRIGGERS,
    )


_RESERVATION_ROLE = """
ALTER TABLE capacity_reservations
ADD COLUMN participant_role text NOT NULL DEFAULT 'accountable'
CHECK (participant_role IN ('accountable','contributor'))
"""

_CONFLICTS = """
CREATE TABLE package_lifecycle_conflicts (
  conflict_id uuid PRIMARY KEY,
  package_id uuid NOT NULL REFERENCES canonical_work_packages(package_id) ON DELETE RESTRICT,
  reason_code text NOT NULL CHECK (char_length(reason_code) BETWEEN 1 AND 80),
  source_type text NOT NULL CHECK (char_length(source_type) BETWEEN 1 AND 40),
  source_id text NOT NULL CHECK (char_length(source_id) BETWEEN 1 AND 160),
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved')),
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  observed_at timestamptz NOT NULL,
  resolved_at timestamptz,
  CHECK ((status='open' AND resolved_at IS NULL) OR
         (status='resolved' AND resolved_at IS NOT NULL))
);
CREATE UNIQUE INDEX uq_package_lifecycle_conflict_open
ON package_lifecycle_conflicts(package_id,reason_code,source_type,source_id)
WHERE status='open'
"""

_DISPOSITION_COMMANDS = """
CREATE TABLE predecessor_cancellation_commands (
  command_id uuid PRIMARY KEY,
  actor_user_id uuid NOT NULL,
  idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 1 AND 128),
  request_hash char(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
  package_id uuid NOT NULL REFERENCES canonical_work_packages(package_id) ON DELETE RESTRICT,
  expected_package_version bigint NOT NULL CHECK (expected_package_version > 0),
  result_package_version bigint NOT NULL CHECK (result_package_version > 0),
  dispositions jsonb NOT NULL,
  occurred_at timestamptz NOT NULL,
  UNIQUE (actor_user_id,idempotency_key)
)
"""

_IMMUTABLE = """
CREATE FUNCTION reject_package_lifecycle_evidence_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  RAISE EXCEPTION 'package lifecycle evidence is immutable';
END $$;
CREATE TRIGGER trg_predecessor_cancellation_commands_immutable
BEFORE UPDATE OR DELETE ON predecessor_cancellation_commands
FOR EACH ROW EXECUTE FUNCTION reject_package_lifecycle_evidence_mutation()
"""

_PREDECESSOR_GUARD = """
CREATE FUNCTION guard_predecessor_cancellation()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  IF NEW.state='cancelled' AND OLD.state<>'cancelled'
     AND current_setting('coeus.predecessor_disposition',true)
         NOT IN ('*',NEW.package_id::text)
     AND EXISTS (SELECT 1 FROM work_package_dependencies
                 WHERE predecessor_package_id=NEW.package_id) THEN
    RAISE EXCEPTION 'predecessor cancellation requires explicit dependant dispositions';
  END IF;
  RETURN NEW;
END $$
"""

_TERMINAL_RECONCILIATION = """
CREATE FUNCTION reconcile_terminal_package()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  IF NEW.state IN ('complete','cancelled') AND OLD.state<>NEW.state THEN
    UPDATE capacity_reservations SET state='released',version=version+1,updated_at=now()
    WHERE package_id=NEW.package_id AND state IN ('held','active');
    UPDATE work_package_participants SET active=false,ended_at=now()
    WHERE package_id=NEW.package_id AND active;
  ELSIF OLD.state IN ('complete','cancelled')
        AND NEW.state NOT IN ('complete','cancelled') THEN
    INSERT INTO package_lifecycle_conflicts
      (conflict_id,package_id,reason_code,source_type,source_id,evidence,observed_at)
    VALUES (gen_random_uuid(),NEW.package_id,'rework_capacity_plan_required',
            'package',NEW.package_id::text,'{}'::jsonb,now())
    ON CONFLICT (package_id,reason_code,source_type,source_id) WHERE status='open'
    DO NOTHING;
  END IF;
  RETURN NEW;
END $$
"""

_PERSON_RECONCILIATION = """
CREATE FUNCTION reconcile_ineligible_participant(person uuid,reason text,source text)
RETURNS void LANGUAGE plpgsql AS $$ BEGIN
  INSERT INTO package_lifecycle_conflicts
    (conflict_id,package_id,reason_code,source_type,source_id,evidence,observed_at)
  SELECT gen_random_uuid(),participant.package_id,reason,'person',source,'{}'::jsonb,now()
  FROM work_package_participants participant
  JOIN canonical_work_packages package ON package.package_id=participant.package_id
  WHERE participant.user_id=person AND participant.active
    AND package.state NOT IN ('complete','cancelled')
  ON CONFLICT (package_id,reason_code,source_type,source_id) WHERE status='open'
  DO NOTHING;
  UPDATE capacity_reservations SET state='released',version=version+1,updated_at=now()
  WHERE user_id=person AND state IN ('held','active');
  UPDATE work_package_participants SET active=false,ended_at=now()
  WHERE user_id=person AND active;
  UPDATE canonical_work_packages SET state='pending',accountable_user_id=NULL,
    blocked_code=NULL,blocked_note='',review_at=NULL,
    version=version+1,updated_at=now()
  WHERE accountable_user_id=person AND state NOT IN ('complete','cancelled');
END $$;
CREATE FUNCTION account_package_reconciliation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  IF (OLD.is_active AND NOT NEW.is_active) OR
     ('Analyst'=ANY(OLD.roles) AND NOT ('Analyst'=ANY(NEW.roles))) THEN
    PERFORM reconcile_ineligible_participant(NEW.user_id,'account_ineligible',NEW.user_id::text);
  END IF; RETURN NEW;
END $$;
CREATE FUNCTION membership_package_reconciliation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  IF OLD.assignment_eligible AND
     (NOT NEW.assignment_eligible OR NEW.state<>'active' OR NEW.valid_until<=now()) THEN
    PERFORM reconcile_ineligible_participant(
      NEW.user_id,'membership_ineligible',NEW.membership_id::text);
  END IF; RETURN NEW;
END $$
"""

_TICKET_RECONCILIATION = """
CREATE FUNCTION ticket_package_reconciliation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  IF OLD.consumes_capacity AND NOT NEW.consumes_capacity THEN
    PERFORM set_config('coeus.predecessor_disposition','*',true);
    UPDATE canonical_work_packages SET state='cancelled',remaining_minutes=0,
      version=version+1,updated_at=now()
    WHERE ticket_id=NEW.ticket_id AND state NOT IN ('complete','cancelled');
  ELSIF NEW.state='JIOC_INTERVENTION_HOLD' AND OLD.state<>NEW.state THEN
    UPDATE capacity_reservations SET state='held',version=version+1,updated_at=now()
    WHERE ticket_id=NEW.ticket_id AND state='active';
  ELSIF NEW.state='REWORK_REQUIRED' AND OLD.state<>NEW.state THEN
    UPDATE capacity_reservations SET state='released',version=version+1,updated_at=now()
    WHERE ticket_id=NEW.ticket_id AND state IN ('held','active') AND starts_at>=now();
  END IF; RETURN NEW;
END $$
"""

_INPUT_CONFLICTS = """
CREATE FUNCTION package_plan_input_changed() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
  IF OLD.estimated_minutes IS DISTINCT FROM NEW.estimated_minutes OR
     OLD.remaining_minutes IS DISTINCT FROM NEW.remaining_minutes OR
     OLD.due_at IS DISTINCT FROM NEW.due_at THEN
    INSERT INTO package_lifecycle_conflicts
      (conflict_id,package_id,reason_code,source_type,source_id,evidence,observed_at)
    VALUES (gen_random_uuid(),NEW.package_id,'capacity_reforecast_required',
            'package',NEW.package_id::text,'{}'::jsonb,now())
    ON CONFLICT (package_id,reason_code,source_type,source_id) WHERE status='open'
    DO NOTHING;
  END IF; RETURN NEW;
END $$
"""

_TRIGGERS = """
CREATE TRIGGER trg_package_predecessor_cancellation BEFORE UPDATE OF state
ON canonical_work_packages FOR EACH ROW EXECUTE FUNCTION guard_predecessor_cancellation();
CREATE TRIGGER trg_package_terminal_reconciliation AFTER UPDATE OF state
ON canonical_work_packages FOR EACH ROW EXECUTE FUNCTION reconcile_terminal_package();
CREATE TRIGGER trg_package_plan_input_changed AFTER UPDATE
ON canonical_work_packages FOR EACH ROW EXECUTE FUNCTION package_plan_input_changed();
CREATE TRIGGER trg_account_package_reconciliation AFTER UPDATE
ON identity_account_projection FOR EACH ROW EXECUTE FUNCTION account_package_reconciliation();
CREATE TRIGGER trg_membership_package_reconciliation AFTER UPDATE
ON team_memberships FOR EACH ROW EXECUTE FUNCTION membership_package_reconciliation();
CREATE TRIGGER trg_ticket_package_reconciliation AFTER UPDATE
ON coeus_ticket_aggregates FOR EACH ROW EXECUTE FUNCTION ticket_package_reconciliation()
"""
