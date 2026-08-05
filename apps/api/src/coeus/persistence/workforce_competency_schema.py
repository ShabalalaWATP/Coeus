"""PostgreSQL schema for verified analyst assignment competencies."""

from collections.abc import Sequence


def workforce_competency_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE IF NOT EXISTS assignment_competencies (
          competency_id uuid PRIMARY KEY,
          user_id uuid NOT NULL,
          capability_id text NOT NULL
            CHECK (char_length(capability_id) BETWEEN 1 AND 120),
          proficiency smallint NOT NULL CHECK (proficiency BETWEEN 1 AND 5),
          verified_by_user_id uuid NOT NULL,
          verified_at timestamptz NOT NULL,
          expires_at timestamptz,
          evidence_reference text NOT NULL DEFAULT ''
            CHECK (char_length(evidence_reference) <= 240),
          version bigint NOT NULL CHECK (version > 0),
          provenance text NOT NULL CHECK (char_length(provenance) BETWEEN 1 AND 120),
          created_at timestamptz NOT NULL,
          updated_at timestamptz NOT NULL,
          CHECK (expires_at IS NULL OR expires_at > verified_at),
          UNIQUE (user_id, capability_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_assignment_competencies_user_current
        ON assignment_competencies(user_id, capability_id, expires_at)
        """,
    )
