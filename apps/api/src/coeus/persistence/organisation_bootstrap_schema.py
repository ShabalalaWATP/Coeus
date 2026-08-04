"""PostgreSQL schema for the permanent one-shot bootstrap marker."""

from collections.abc import Sequence


def organisation_bootstrap_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE IF NOT EXISTS organisation_bootstrap_state (
          singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
          ceremony_id uuid NOT NULL UNIQUE,
          completed_by_user_id uuid NOT NULL,
          completed_at timestamptz NOT NULL,
          root_unit_id uuid NOT NULL UNIQUE REFERENCES organisation_units(unit_id)
            ON DELETE RESTRICT
        )
        """,
    )
