"""Schema statements for exact-candidate organisation cutover evidence."""


def cutover_activation_schema_statements() -> tuple[str, ...]:
    return (
        _MANIFESTS,
        _RELEASE,
        _APPROVALS,
        _SLICE_STATE,
        _EVIDENCE,
        _CHECKPOINTS,
        _CHECKPOINT_EVENTS,
        _WRITER_FENCES,
        _RECOVERY,
        _IMMUTABLE_FUNCTION,
        _SOURCE_WRITE_FUNCTION,
        _SOURCE_WRITE_TRIGGER,
        _TICKET_WRITE_FUNCTION,
        _TICKET_WRITE_TRIGGER,
        _TICKET_PARITY_FUNCTION,
        _TICKET_PARITY_TRIGGER,
        *_IMMUTABLE_TRIGGERS,
    )


_MANIFESTS = """
CREATE TABLE organisation_cutover_manifests (
  candidate_hash text PRIMARY KEY CHECK (candidate_hash ~ '^[0-9a-f]{64}$'),
  source_revision text NOT NULL CHECK (char_length(source_revision) BETWEEN 1 AND 128),
  schema_head text NOT NULL CHECK (char_length(schema_head) BETWEEN 1 AND 128),
  organisation_parity_hash text NOT NULL CHECK (organisation_parity_hash ~ '^[0-9a-f]{64}$'),
  calendar_parity_hash text NOT NULL CHECK (calendar_parity_hash ~ '^[0-9a-f]{64}$'),
  task_capacity_parity_hash text NOT NULL CHECK (task_capacity_parity_hash ~ '^[0-9a-f]{64}$'),
  routing_evaluation_release text NOT NULL
    CHECK (char_length(routing_evaluation_release) BETWEEN 1 AND 128),
  routing_evaluation_hash text NOT NULL CHECK (routing_evaluation_hash ~ '^[0-9a-f]{64}$'),
  protected_checks_reference text NOT NULL
    CHECK (char_length(protected_checks_reference) BETWEEN 1 AND 128),
  protected_checks_hash text NOT NULL CHECK (protected_checks_hash ~ '^[0-9a-f]{64}$'),
  browser_evidence_hash text NOT NULL CHECK (browser_evidence_hash ~ '^[0-9a-f]{64}$'),
  security_review_reference text NOT NULL
    CHECK (char_length(security_review_reference) BETWEEN 1 AND 128),
  security_review_hash text NOT NULL CHECK (security_review_hash ~ '^[0-9a-f]{64}$'),
  backup_restore_hash text NOT NULL CHECK (backup_restore_hash ~ '^[0-9a-f]{64}$'),
  proposed_by_user_id uuid NOT NULL,
  proposed_at timestamptz NOT NULL
)
"""

_RELEASE = """
CREATE TABLE organisation_cutover_release (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  candidate_hash text NOT NULL REFERENCES organisation_cutover_manifests(candidate_hash),
  version bigint NOT NULL CHECK (version > 0),
  updated_at timestamptz NOT NULL
)
"""

_SLICE_STATE = """
CREATE TABLE organisation_cutover_slice_state (
  candidate_hash text NOT NULL REFERENCES organisation_cutover_manifests(candidate_hash),
  slice text NOT NULL CHECK (slice IN ('organisation','calendar','task_capacity')),
  status text NOT NULL CHECK (status IN ('previewed','approved','active')),
  preview_hash text NOT NULL CHECK (preview_hash ~ '^[0-9a-f]{64}$'),
  proposed_by_user_id uuid NOT NULL,
  previewed_at timestamptz NOT NULL,
  preview_expires_at timestamptz NOT NULL,
  source_snapshot_hash text NOT NULL CHECK (source_snapshot_hash ~ '^[0-9a-f]{64}$'),
  target_snapshot_hash text NOT NULL CHECK (target_snapshot_hash ~ '^[0-9a-f]{64}$'),
  visibility_hash text NOT NULL CHECK (visibility_hash ~ '^[0-9a-f]{64}$'),
  security_approval_id uuid,
  security_approval_role text NOT NULL DEFAULT 'security_review'
    CHECK (security_approval_role='security_review'),
  release_approval_id uuid,
  release_approval_role text NOT NULL DEFAULT 'release_authority'
    CHECK (release_approval_role='release_authority'),
  approved_at timestamptz,
  activated_by_user_id uuid,
  activated_at timestamptz,
  version bigint NOT NULL CHECK (version > 0),
  PRIMARY KEY (candidate_hash,slice),
  FOREIGN KEY (candidate_hash,slice,security_approval_id,security_approval_role)
    REFERENCES organisation_cutover_approvals(candidate_hash,slice,approval_id,approval_role),
  FOREIGN KEY (candidate_hash,slice,release_approval_id,release_approval_role)
    REFERENCES organisation_cutover_approvals(candidate_hash,slice,approval_id,approval_role),
  CHECK (previewed_at < preview_expires_at),
  CHECK ((status='previewed' AND security_approval_id IS NULL
          AND release_approval_id IS NULL AND activated_at IS NULL)
      OR (status='approved' AND security_approval_id IS NOT NULL
          AND release_approval_id IS NOT NULL AND approved_at IS NOT NULL
          AND activated_at IS NULL)
      OR (status='active' AND security_approval_id IS NOT NULL
          AND release_approval_id IS NOT NULL AND approved_at IS NOT NULL
          AND activated_by_user_id IS NOT NULL AND activated_at IS NOT NULL))
)
"""

_APPROVALS = """
CREATE TABLE organisation_cutover_approvals (
  approval_id uuid PRIMARY KEY,
  candidate_hash text NOT NULL REFERENCES organisation_cutover_manifests(candidate_hash),
  slice text NOT NULL CHECK (slice IN ('organisation','calendar','task_capacity')),
  approval_role text NOT NULL CHECK (approval_role IN ('security_review','release_authority')),
  preview_hash text NOT NULL CHECK (preview_hash ~ '^[0-9a-f]{64}$'),
  approved_by_user_id uuid NOT NULL,
  approved_at timestamptz NOT NULL,
  UNIQUE (candidate_hash,slice,approval_role),
  UNIQUE (candidate_hash,approval_id),
  UNIQUE (candidate_hash,slice,approval_id,approval_role)
)
"""

_EVIDENCE = """
CREATE TABLE organisation_cutover_evidence (
  evidence_id uuid PRIMARY KEY,
  candidate_hash text NOT NULL REFERENCES organisation_cutover_manifests(candidate_hash),
  slice text NOT NULL CHECK (slice IN ('organisation','calendar','task_capacity')),
  evidence_kind text NOT NULL CHECK (evidence_kind IN
    ('preview','approval','quiescence','visibility_parity','activation','recovery')),
  evidence_hash text NOT NULL CHECK (evidence_hash ~ '^[0-9a-f]{64}$'),
  source_snapshot_hash text CHECK (source_snapshot_hash ~ '^[0-9a-f]{64}$'),
  target_snapshot_hash text CHECK (target_snapshot_hash ~ '^[0-9a-f]{64}$'),
  actor_user_id uuid NOT NULL,
  payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
  recorded_at timestamptz NOT NULL,
  UNIQUE (candidate_hash,slice,evidence_kind,evidence_hash)
)
"""

_CHECKPOINTS = """
CREATE TABLE organisation_cutover_checkpoints (
  checkpoint_id uuid PRIMARY KEY,
  candidate_hash text NOT NULL REFERENCES organisation_cutover_manifests(candidate_hash),
  slice text NOT NULL CHECK (slice IN ('organisation','calendar','task_capacity')),
  status text NOT NULL CHECK (status IN ('pending','running','completed','failed')),
  cursor_token text CHECK (cursor_token IS NULL OR char_length(cursor_token) BETWEEN 1 AND 256),
  source_count integer NOT NULL CHECK (source_count BETWEEN 0 AND 1000000),
  target_count integer NOT NULL CHECK (target_count BETWEEN 0 AND 1000000),
  source_snapshot_hash text NOT NULL CHECK (source_snapshot_hash ~ '^[0-9a-f]{64}$'),
  target_snapshot_hash text NOT NULL CHECK (target_snapshot_hash ~ '^[0-9a-f]{64}$'),
  lease_token uuid,
  lease_expires_at timestamptz,
  version bigint NOT NULL CHECK (version > 0),
  started_at timestamptz,
  completed_at timestamptz,
  failure_code text CHECK (failure_code IS NULL OR char_length(failure_code) BETWEEN 1 AND 64),
  UNIQUE (candidate_hash,slice),
  CHECK ((status='running')=(lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)),
  CHECK ((status='completed')=(completed_at IS NOT NULL))
)
"""

_CHECKPOINT_EVENTS = """
CREATE TABLE organisation_cutover_checkpoint_events (
  event_id uuid PRIMARY KEY,
  checkpoint_id uuid NOT NULL REFERENCES organisation_cutover_checkpoints(checkpoint_id),
  checkpoint_version bigint NOT NULL CHECK (checkpoint_version > 0),
  event_type text NOT NULL CHECK (event_type IN ('started','resumed','completed','failed')),
  actor_user_id uuid NOT NULL,
  evidence_hash text NOT NULL CHECK (evidence_hash ~ '^[0-9a-f]{64}$'),
  occurred_at timestamptz NOT NULL,
  UNIQUE (checkpoint_id,checkpoint_version)
)
"""

_WRITER_FENCES = """
CREATE TABLE organisation_cutover_writer_fences (
  slice text PRIMARY KEY CHECK (slice IN ('organisation','calendar','task_capacity')),
  candidate_hash text NOT NULL REFERENCES organisation_cutover_manifests(candidate_hash),
  state text NOT NULL CHECK (state IN ('open','quiescing','fenced','target_authoritative')),
  fence_epoch bigint NOT NULL CHECK (fence_epoch > 0),
  owner_token uuid,
  quiesced_by_user_id uuid,
  quiesced_at timestamptz,
  updated_at timestamptz NOT NULL,
  CHECK ((state IN ('quiescing','fenced'))=(owner_token IS NOT NULL)),
  CHECK ((state IN ('fenced','target_authoritative'))=(quiesced_at IS NOT NULL))
)
"""

_RECOVERY = """
CREATE TABLE organisation_cutover_recovery_events (
  recovery_id uuid PRIMARY KEY,
  candidate_hash text NOT NULL REFERENCES organisation_cutover_manifests(candidate_hash),
  slice text NOT NULL CHECK (slice IN ('organisation','calendar','task_capacity')),
  checkpoint_id uuid REFERENCES organisation_cutover_checkpoints(checkpoint_id),
  action text NOT NULL CHECK (action IN ('resume','forward_repair','abort_before_activation')),
  reason_code text NOT NULL CHECK (char_length(reason_code) BETWEEN 1 AND 64),
  actor_user_id uuid NOT NULL,
  prior_state_hash text NOT NULL CHECK (prior_state_hash ~ '^[0-9a-f]{64}$'),
  result_state_hash text NOT NULL CHECK (result_state_hash ~ '^[0-9a-f]{64}$'),
  occurred_at timestamptz NOT NULL
)
"""

_IMMUTABLE_FUNCTION = """
CREATE FUNCTION reject_cutover_evidence_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'cutover evidence is immutable' USING ERRCODE='55000';
END;
$$ LANGUAGE plpgsql
"""

_SOURCE_WRITE_FUNCTION = """
CREATE FUNCTION reject_fenced_cutover_source_write() RETURNS trigger AS $$
DECLARE selected_slice text;
BEGIN
  selected_slice := CASE
    WHEN coalesce(NEW.namespace,OLD.namespace) IN ('teams','user_profiles')
      THEN 'organisation'
    WHEN coalesce(NEW.namespace,OLD.namespace)='team_calendar' THEN 'calendar'
    ELSE NULL
  END;
  IF selected_slice IS NOT NULL AND EXISTS (
    SELECT 1 FROM organisation_cutover_writer_fences
    WHERE slice=selected_slice AND state IN ('quiescing','fenced','target_authoritative')
  ) THEN
    RAISE EXCEPTION 'legacy cutover source is read-only' USING ERRCODE='55000';
  END IF;
  RETURN coalesce(NEW,OLD);
END;
$$ LANGUAGE plpgsql
"""

_SOURCE_WRITE_TRIGGER = """
CREATE TRIGGER trg_coeus_state_cutover_writer_fence
BEFORE INSERT OR UPDATE OR DELETE ON coeus_state
FOR EACH ROW EXECUTE FUNCTION reject_fenced_cutover_source_write()
"""

_TICKET_WRITE_FUNCTION = """
CREATE FUNCTION reject_fenced_task_capacity_write() RETURNS trigger AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM organisation_cutover_writer_fences
    WHERE slice='task_capacity' AND state IN ('quiescing','fenced')
  ) THEN
    RAISE EXCEPTION 'task and capacity source is quiesced' USING ERRCODE='55000';
  END IF;
  RETURN coalesce(NEW,OLD);
END;
$$ LANGUAGE plpgsql
"""

_TICKET_WRITE_TRIGGER = """
CREATE TRIGGER trg_ticket_task_capacity_writer_fence
BEFORE INSERT OR UPDATE OR DELETE ON coeus_ticket_aggregates
FOR EACH ROW EXECUTE FUNCTION reject_fenced_task_capacity_write()
"""

_TICKET_PARITY_FUNCTION = """
CREATE FUNCTION require_active_task_capacity_projection() RETURNS trigger AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM organisation_cutover_writer_fences
    WHERE slice='task_capacity' AND state='target_authoritative'
  ) AND NEW.consumes_capacity AND NEW.state IN (
    'ANALYST_ASSIGNMENT','ANALYST_IN_PROGRESS','MANAGER_APPROVAL','QC_REVIEW',
    'REWORK_REQUIRED','DISSEMINATION_READY','MANAGER_REANALYSIS_REVIEW',
    'JIOC_REANALYSIS_ADJUDICATION'
  ) AND NOT EXISTS (
    SELECT 1 FROM team_task_ownership ownership
    WHERE ownership.ticket_id=NEW.ticket_id
      AND ownership.state NOT IN ('cancelled','ownership_unresolved')
  ) THEN
    RAISE EXCEPTION 'active task-capacity projection is missing' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""

_TICKET_PARITY_TRIGGER = """
CREATE CONSTRAINT TRIGGER trg_ticket_active_task_capacity_projection
AFTER INSERT OR UPDATE ON coeus_ticket_aggregates DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION require_active_task_capacity_projection()
"""

_IMMUTABLE_TRIGGERS = tuple(
    f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} "
    "FOR EACH ROW EXECUTE FUNCTION reject_cutover_evidence_mutation()"
    for table in (
        "organisation_cutover_manifests",
        "organisation_cutover_approvals",
        "organisation_cutover_evidence",
        "organisation_cutover_checkpoint_events",
        "organisation_cutover_recovery_events",
    )
)
