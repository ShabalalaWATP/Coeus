"""Lifecycle triggers for eligibility and scheduling input changes."""

from collections.abc import Sequence


def package_lifecycle_input_statements() -> Sequence[str]:
    return (_ELIGIBILITY_FUNCTIONS, _CALENDAR_FUNCTIONS, _TRIGGERS)


_ELIGIBILITY_FUNCTIONS = """
CREATE FUNCTION team_package_reconciliation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE person uuid; BEGIN
  IF OLD.is_active AND NOT NEW.is_active THEN
    FOR person IN SELECT DISTINCT participant.user_id
      FROM work_package_participants participant
      JOIN canonical_work_packages package ON package.package_id=participant.package_id
      WHERE participant.active AND package.owning_unit_id=NEW.unit_id
    LOOP
      PERFORM reconcile_ineligible_participant(
        person,'team_inactive',NEW.unit_id::text);
    END LOOP;
  END IF; RETURN NEW;
END $$;

CREATE FUNCTION competency_package_reconciliation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE item record; changed record; BEGIN
  IF TG_OP='DELETE' THEN changed := OLD; ELSE changed := NEW; END IF;
  IF TG_OP='DELETE' OR
     (changed.expires_at IS NOT NULL AND changed.expires_at<=now()) THEN
    FOR item IN SELECT DISTINCT participant.package_id
      FROM work_package_participants participant
      JOIN canonical_work_packages package ON package.package_id=participant.package_id
      WHERE participant.user_id=changed.user_id AND participant.active
        AND package.state NOT IN ('complete','cancelled')
    LOOP
      INSERT INTO package_lifecycle_conflicts
        (conflict_id,package_id,reason_code,source_type,source_id,evidence,observed_at)
      VALUES (gen_random_uuid(),item.package_id,'competency_review_required',
              'competency',changed.competency_id::text,'{}'::jsonb,now())
      ON CONFLICT (package_id,reason_code,source_type,source_id) WHERE status='open'
      DO NOTHING;
    END LOOP;
    UPDATE capacity_reservations SET state='held',version=version+1,updated_at=now()
    WHERE user_id=changed.user_id AND state='active' AND ends_at>now();
  END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION capability_package_reconciliation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE item record; changed record; BEGIN
  IF TG_OP='DELETE' THEN changed := OLD; ELSE changed := NEW; END IF;
  IF TG_OP='DELETE' OR
     (changed.valid_until IS NOT NULL AND changed.valid_until<=now()) THEN
    FOR item IN SELECT package.package_id FROM canonical_work_packages package
      JOIN team_delivery_profiles profile ON profile.unit_id=package.owning_unit_id
      WHERE profile.profile_id=changed.profile_id
        AND package.state NOT IN ('complete','cancelled')
    LOOP
      INSERT INTO package_lifecycle_conflicts
        (conflict_id,package_id,reason_code,source_type,source_id,evidence,observed_at)
      VALUES (gen_random_uuid(),item.package_id,'capability_review_required',
              'capability',changed.coverage_id::text,'{}'::jsonb,now())
      ON CONFLICT (package_id,reason_code,source_type,source_id) WHERE status='open'
      DO NOTHING;
    END LOOP;
  END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$
"""

_CALENDAR_FUNCTIONS = """
CREATE FUNCTION calendar_package_reconciliation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE person uuid; source text; BEGIN
  IF TG_TABLE_NAME='calendar_event_exceptions' THEN
    SELECT owner_user_id INTO person FROM calendar_events
    WHERE event_id=CASE WHEN TG_OP='DELETE' THEN OLD.event_id ELSE NEW.event_id END;
    source := (CASE WHEN TG_OP='DELETE' THEN OLD.exception_id ELSE NEW.exception_id END)::text;
  ELSE
    person := CASE WHEN TG_OP='DELETE' THEN OLD.owner_user_id ELSE NEW.owner_user_id END;
    source := (CASE WHEN TG_OP='DELETE' THEN OLD.event_id ELSE NEW.event_id END)::text;
  END IF;
  INSERT INTO package_lifecycle_conflicts
    (conflict_id,package_id,reason_code,source_type,source_id,evidence,observed_at)
  SELECT gen_random_uuid(),reservation.package_id,'calendar_reforecast_required',
         'calendar',source,'{}'::jsonb,now()
  FROM capacity_reservations reservation
  JOIN canonical_work_packages package ON package.package_id=reservation.package_id
  WHERE reservation.user_id=person AND reservation.state IN ('held','active')
    AND package.state NOT IN ('complete','cancelled')
  ON CONFLICT (package_id,reason_code,source_type,source_id) WHERE status='open'
  DO NOTHING;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$
"""

_TRIGGERS = """
CREATE TRIGGER trg_team_package_reconciliation AFTER UPDATE OF is_active
ON organisation_units FOR EACH ROW EXECUTE FUNCTION team_package_reconciliation();
CREATE TRIGGER trg_competency_package_reconciliation AFTER UPDATE OR DELETE
ON assignment_competencies FOR EACH ROW EXECUTE FUNCTION competency_package_reconciliation();
CREATE TRIGGER trg_capability_package_reconciliation AFTER UPDATE OR DELETE
ON team_capability_coverage FOR EACH ROW EXECUTE FUNCTION capability_package_reconciliation();
CREATE TRIGGER trg_calendar_package_reconciliation AFTER INSERT OR UPDATE OR DELETE
ON calendar_events FOR EACH ROW EXECUTE FUNCTION calendar_package_reconciliation();
CREATE TRIGGER trg_calendar_exception_package_reconciliation AFTER INSERT OR UPDATE OR DELETE
ON calendar_event_exceptions FOR EACH ROW EXECUTE FUNCTION calendar_package_reconciliation()
"""
