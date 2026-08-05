"""PostgreSQL schema for versioned demand and expiring assignment holds."""


def assignment_recommendation_schema_statements() -> tuple[str, ...]:
    return (
        _ESTIMATES,
        _RECOMMENDATIONS,
        _CANDIDATES,
        _HOLDS,
        _DECISIONS,
        _ACTIVE_HOLD_INDEX,
        _ESTIMATE_IMMUTABILITY,
        _DECISION_IMMUTABILITY,
    )


_ESTIMATES = """
CREATE TABLE assignment_demand_estimates (
  estimate_id uuid PRIMARY KEY,
  ticket_id uuid NOT NULL,
  workflow_leg text NOT NULL CHECK (workflow_leg IN ('rfa','cm_collection')),
  version bigint NOT NULL CHECK (version > 0),
  effort_min_minutes integer NOT NULL CHECK (effort_min_minutes > 0 AND effort_min_minutes % 15=0),
  effort_max_minutes integer NOT NULL CHECK (
    effort_max_minutes >= effort_min_minutes AND effort_max_minutes % 15=0),
  window_start timestamptz NOT NULL,
  deadline timestamptz NOT NULL,
  capability_ids text[] NOT NULL CHECK (cardinality(capability_ids) BETWEEN 1 AND 12),
  created_by_user_id uuid NOT NULL,
  source_hash char(64) NOT NULL CHECK (source_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL,
  CHECK (window_start < deadline),
  UNIQUE (ticket_id,workflow_leg,version)
)
"""

_RECOMMENDATIONS = """
CREATE TABLE assignment_recommendations (
  recommendation_id uuid PRIMARY KEY,
  estimate_id uuid NOT NULL REFERENCES assignment_demand_estimates(estimate_id) ON DELETE RESTRICT,
  actor_user_id uuid NOT NULL,
  ticket_version bigint NOT NULL CHECK (ticket_version > 0),
  preview_hash char(64) NOT NULL CHECK (preview_hash ~ '^[0-9a-f]{64}$'),
  exclusion_counts jsonb NOT NULL,
  state text NOT NULL CHECK (state IN ('prepared','accepted','expired','cancelled')),
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  CHECK (created_at < expires_at)
)
"""

_CANDIDATES = """
CREATE TABLE assignment_recommendation_candidates (
  recommendation_id uuid NOT NULL REFERENCES assignment_recommendations(recommendation_id)
    ON DELETE RESTRICT,
  unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
  analyst_user_id uuid NOT NULL,
  rank integer NOT NULL CHECK (rank BETWEEN 1 AND 100),
  assignable_minutes integer NOT NULL CHECK (assignable_minutes >= 0 AND assignable_minutes % 15=0),
  active_wip integer NOT NULL CHECK (active_wip >= 0),
  explanation_codes text[] NOT NULL,
  evidence_hash char(64) NOT NULL CHECK (evidence_hash ~ '^[0-9a-f]{64}$'),
  PRIMARY KEY (recommendation_id,analyst_user_id),
  UNIQUE (recommendation_id,rank)
)
"""

_HOLDS = """
CREATE TABLE assignment_demand_holds (
  hold_id uuid PRIMARY KEY,
  recommendation_id uuid NOT NULL UNIQUE
    REFERENCES assignment_recommendations(recommendation_id) ON DELETE RESTRICT,
  ticket_id uuid NOT NULL,
  unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
  held_minutes integer NOT NULL CHECK (held_minutes > 0 AND held_minutes % 15=0),
  starts_at timestamptz NOT NULL,
  ends_at timestamptz NOT NULL,
  state text NOT NULL CHECK (state IN ('active','consumed','released','expired')),
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  CHECK (starts_at < ends_at AND created_at < expires_at)
)
"""

_DECISIONS = """
CREATE TABLE assignment_recommendation_decisions (
  decision_id uuid PRIMARY KEY,
  recommendation_id uuid NOT NULL UNIQUE
    REFERENCES assignment_recommendations(recommendation_id) ON DELETE RESTRICT,
  actor_user_id uuid NOT NULL,
  selected_unit_id uuid NOT NULL REFERENCES organisation_units(unit_id) ON DELETE RESTRICT,
  selected_analyst_user_id uuid NOT NULL,
  recommended_analyst_user_id uuid NOT NULL,
  decision_type text NOT NULL CHECK (decision_type IN ('accepted','soft_override')),
  reason text NOT NULL CHECK (char_length(reason) <= 500),
  reason_hash char(64) NOT NULL CHECK (reason_hash ~ '^[0-9a-f]{64}$'),
  occurred_at timestamptz NOT NULL,
  CHECK ((decision_type='accepted' AND reason='') OR
         (decision_type='soft_override' AND char_length(reason) BETWEEN 10 AND 500))
)
"""

_ACTIVE_HOLD_INDEX = """
CREATE INDEX idx_assignment_demand_holds_active
ON assignment_demand_holds(unit_id,starts_at,ends_at,expires_at)
WHERE state='active'
"""

_ESTIMATE_IMMUTABILITY = """
CREATE TRIGGER trg_assignment_demand_estimates_immutable
BEFORE UPDATE OR DELETE ON assignment_demand_estimates
FOR EACH ROW EXECUTE FUNCTION reject_work_package_history_mutation()
"""

_DECISION_IMMUTABILITY = """
CREATE TRIGGER trg_assignment_recommendation_decisions_immutable
BEFORE UPDATE OR DELETE ON assignment_recommendation_decisions
FOR EACH ROW EXECUTE FUNCTION reject_work_package_history_mutation()
"""
