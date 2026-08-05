"""Durable proposal, disposition, hold and command evidence for work transfers."""

# ruff: noqa: E501

from collections.abc import Sequence


def workflow_leg_transfer_schema_statements() -> Sequence[str]:
    return (
        _TRANSFERS,
        _DISPOSITIONS,
        _HOLDS,
        _COMMANDS,
        _INDEXES,
        _IMMUTABLE,
        _TRANSFER_PROTECTION,
        _TRIGGERS,
    )


_TRANSFERS = """
CREATE TABLE workflow_leg_transfers (
 transfer_id uuid PRIMARY KEY,ticket_id uuid NOT NULL,
 workflow_leg text NOT NULL CHECK(workflow_leg IN ('rfa','cm_collection','cm_analysis','qc')),
 source_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
 target_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
 target_user_id uuid NOT NULL,source_manager_user_id uuid NOT NULL,target_manager_user_id uuid,
 state text NOT NULL CHECK(state IN ('proposed','accepted','rejected','cancelled','expired')),
 expected_ownership_version bigint NOT NULL CHECK(expected_ownership_version>0),
 result_ownership_version bigint,expected_ticket_version bigint NOT NULL CHECK(expected_ticket_version>0),
 result_ticket_version bigint,expected_ticket_source_hash char(64) NOT NULL,
 source_grant_id uuid NOT NULL,source_grant_version bigint NOT NULL CHECK(source_grant_version>0),
 proposal_hash char(64) NOT NULL,preview_hash char(64) NOT NULL,
 expires_at timestamptz NOT NULL,reason text NOT NULL CHECK(char_length(reason)<=500),
 decision_reason text NOT NULL DEFAULT '' CHECK(char_length(decision_reason)<=500),
 version bigint NOT NULL CHECK(version>0),created_at timestamptz NOT NULL,updated_at timestamptz NOT NULL,
 decided_at timestamptz,CONSTRAINT ck_workflow_transfer_units CHECK(source_unit_id<>target_unit_id),
 CONSTRAINT ck_workflow_transfer_decision CHECK((state='proposed' AND decided_at IS NULL) OR
 (state<>'proposed' AND decided_at IS NOT NULL))
)
"""

_DISPOSITIONS = """
CREATE TABLE workflow_leg_transfer_packages (
 transfer_id uuid NOT NULL REFERENCES workflow_leg_transfers(transfer_id) ON DELETE RESTRICT,
 package_id uuid NOT NULL REFERENCES canonical_work_packages(package_id) ON DELETE RESTRICT,
 disposition text NOT NULL CHECK(disposition IN ('transfer','complete','cancel','retain')),
 expected_version bigint NOT NULL CHECK(expected_version>0),reservation_id uuid,
 reservation_idempotency_key text CHECK(char_length(reservation_idempotency_key) BETWEEN 1 AND 128),
 starts_at timestamptz,ends_at timestamptz,reserved_minutes integer,
 PRIMARY KEY(transfer_id,package_id),CONSTRAINT ck_transfer_reservation_plan CHECK(
  (disposition='transfer' AND reservation_id IS NOT NULL AND reservation_idempotency_key IS NOT NULL
   AND starts_at IS NOT NULL AND ends_at IS NOT NULL AND starts_at<ends_at
   AND reserved_minutes>0 AND reserved_minutes%15=0) OR
  (disposition<>'transfer' AND reservation_id IS NULL AND reservation_idempotency_key IS NULL
   AND starts_at IS NULL AND ends_at IS NULL AND reserved_minutes IS NULL))
)
"""

_HOLDS = """
CREATE TABLE workflow_leg_transfer_team_holds (
 hold_id uuid PRIMARY KEY,transfer_id uuid NOT NULL,
 package_id uuid NOT NULL,target_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id),
 starts_at timestamptz NOT NULL,ends_at timestamptz NOT NULL,reserved_minutes integer NOT NULL,
 state text NOT NULL CHECK(state IN ('active','released','cancelled')),
 created_at timestamptz NOT NULL,released_at timestamptz,
 UNIQUE(transfer_id,package_id),FOREIGN KEY(transfer_id,package_id)
 REFERENCES workflow_leg_transfer_packages(transfer_id,package_id) ON DELETE RESTRICT,
 CHECK(starts_at<ends_at AND reserved_minutes>0 AND reserved_minutes%15=0)
)
"""

_COMMANDS = """
CREATE TABLE workflow_leg_transfer_commands (
 command_id uuid PRIMARY KEY,actor_user_id uuid NOT NULL,idempotency_key text NOT NULL,
 transfer_id uuid NOT NULL REFERENCES workflow_leg_transfers(transfer_id) ON DELETE RESTRICT,
 action text NOT NULL CHECK(action IN ('propose','accept','reject','cancel','expire')),
 request_hash char(64) NOT NULL,result_state text NOT NULL,result_version bigint NOT NULL,
 occurred_at timestamptz NOT NULL,UNIQUE(actor_user_id,idempotency_key)
)
"""

_INDEXES = """
CREATE INDEX idx_workflow_leg_transfers_source ON workflow_leg_transfers(source_unit_id,state,expires_at);
CREATE INDEX idx_workflow_leg_transfers_target ON workflow_leg_transfers(target_unit_id,state,expires_at)
"""

_IMMUTABLE = """
CREATE FUNCTION reject_workflow_leg_transfer_evidence_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'workflow-leg transfer evidence is immutable'; END $$
"""

_TRANSFER_PROTECTION = """
CREATE FUNCTION protect_workflow_leg_transfer_proposal() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'workflow-leg transfer evidence is immutable'; END IF;
 IF OLD.state<>'proposed' OR NEW.state='proposed' OR NEW.version<>OLD.version+1 OR
    NEW.ticket_id<>OLD.ticket_id OR NEW.workflow_leg<>OLD.workflow_leg OR
    NEW.source_unit_id<>OLD.source_unit_id OR NEW.target_unit_id<>OLD.target_unit_id OR
    NEW.target_user_id<>OLD.target_user_id OR
    NEW.source_manager_user_id<>OLD.source_manager_user_id OR
    NEW.expected_ownership_version<>OLD.expected_ownership_version OR
    NEW.expected_ticket_version<>OLD.expected_ticket_version OR
    NEW.expected_ticket_source_hash<>OLD.expected_ticket_source_hash OR
    NEW.source_grant_id<>OLD.source_grant_id OR
    NEW.source_grant_version<>OLD.source_grant_version OR
    NEW.proposal_hash<>OLD.proposal_hash OR NEW.preview_hash<>OLD.preview_hash OR
    NEW.expires_at<>OLD.expires_at OR NEW.reason<>OLD.reason OR
    NEW.created_at<>OLD.created_at THEN
  RAISE EXCEPTION 'workflow-leg transfer proposal evidence is immutable';
 END IF;
 RETURN NEW;
END $$
"""

_TRIGGERS = """
CREATE TRIGGER trg_workflow_leg_transfer_packages_immutable BEFORE UPDATE OR DELETE
 ON workflow_leg_transfer_packages FOR EACH ROW EXECUTE FUNCTION reject_workflow_leg_transfer_evidence_mutation();
CREATE TRIGGER trg_workflow_leg_transfer_commands_immutable BEFORE UPDATE OR DELETE
 ON workflow_leg_transfer_commands FOR EACH ROW EXECUTE FUNCTION reject_workflow_leg_transfer_evidence_mutation();
CREATE TRIGGER trg_workflow_leg_transfer_proposal_protected BEFORE UPDATE OR DELETE
 ON workflow_leg_transfers FOR EACH ROW EXECUTE FUNCTION protect_workflow_leg_transfer_proposal()
"""
