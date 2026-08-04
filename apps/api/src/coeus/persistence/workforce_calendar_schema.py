"""PostgreSQL schema for canonical personal and team calendar events."""

from collections.abc import Sequence


def workforce_calendar_schema_statements() -> Sequence[str]:
    return (
        """
        CREATE TABLE calendar_events (
            event_id uuid PRIMARY KEY,
            owner_user_id uuid NOT NULL,
            source varchar(24) NOT NULL CHECK (
                source IN ('personal','manager','team','task','external','legacy')
            ),
            activity_category varchar(32) NOT NULL CHECK (
                activity_category IN (
                    'leave','training','duty','appointment','meeting','task','other'
                )
            ),
            starts_at timestamptz,
            ends_at timestamptz,
            all_day_start date,
            all_day_end date,
            time_zone varchar(64) NOT NULL,
            availability_effect varchar(16) NOT NULL CHECK (
                availability_effect IN ('available','partial','unavailable')
            ),
            privacy_level varchar(20) NOT NULL CHECK (
                privacy_level IN ('private','team_summary','team_detail')
            ),
            note varchar(280) NOT NULL DEFAULT '',
            recurrence_rule jsonb,
            status varchar(16) NOT NULL DEFAULT 'active' CHECK (
                status IN ('active','cancelled','conflicted')
            ),
            manager_scope_unit_id uuid REFERENCES organisation_units(unit_id),
            created_by_user_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
            cancelled_at timestamptz,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            provenance varchar(32) NOT NULL DEFAULT 'canonical',
            CHECK (
                (starts_at IS NOT NULL AND ends_at IS NOT NULL
                    AND all_day_start IS NULL AND all_day_end IS NULL
                    AND ends_at > starts_at)
                OR
                (starts_at IS NULL AND ends_at IS NULL
                    AND all_day_start IS NOT NULL AND all_day_end IS NOT NULL
                    AND all_day_end > all_day_start)
            ),
            CHECK (recurrence_rule IS NULL OR octet_length(recurrence_rule::text) <= 2048),
            CHECK ((status = 'cancelled') = (cancelled_at IS NOT NULL))
        )
        """,
        """
        CREATE TABLE calendar_event_scopes (
            scope_id uuid PRIMARY KEY,
            event_id uuid NOT NULL REFERENCES calendar_events(event_id),
            scope_type varchar(24) NOT NULL CHECK (
                scope_type IN ('owner_global','home_unit','team_participant')
            ),
            subject_user_id uuid,
            unit_id uuid REFERENCES organisation_units(unit_id),
            created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
            CHECK (
                (scope_type = 'owner_global' AND subject_user_id IS NOT NULL AND unit_id IS NULL)
                OR
                (scope_type IN ('home_unit','team_participant')
                    AND subject_user_id IS NOT NULL AND unit_id IS NOT NULL)
            ),
            UNIQUE(event_id, scope_type, subject_user_id, unit_id)
        )
        """,
        """
        CREATE TABLE calendar_event_exceptions (
            exception_id uuid PRIMARY KEY,
            event_id uuid NOT NULL REFERENCES calendar_events(event_id),
            occurrence_key varchar(64) NOT NULL,
            action varchar(16) NOT NULL CHECK (action IN ('change','cancel')),
            replacement jsonb,
            version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
            created_by_user_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
            UNIQUE(event_id, occurrence_key),
            CHECK (replacement IS NULL OR octet_length(replacement::text) <= 8192)
        )
        """,
        """
        CREATE TABLE calendar_event_versions (
            history_id uuid PRIMARY KEY,
            event_id uuid NOT NULL REFERENCES calendar_events(event_id),
            event_version integer NOT NULL CHECK (event_version >= 1),
            snapshot jsonb NOT NULL CHECK (octet_length(snapshot::text) <= 8192),
            changed_by_user_id uuid NOT NULL,
            changed_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
            change_reason_hash char(64) NOT NULL,
            UNIQUE(event_id, event_version)
        )
        """,
        """
        CREATE TABLE calendar_event_commands (
            command_id uuid PRIMARY KEY,
            actor_user_id uuid NOT NULL,
            idempotency_key varchar(128) NOT NULL,
            command_type varchar(16) NOT NULL CHECK (
                command_type IN ('create','update','cancel')
            ),
            request_hash char(64) NOT NULL,
            event_id uuid NOT NULL REFERENCES calendar_events(event_id),
            result_version integer NOT NULL CHECK (result_version >= 1),
            created_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
            UNIQUE(actor_user_id, idempotency_key)
        )
        """,
        "CREATE INDEX ix_calendar_events_owner_window "
        "ON calendar_events(owner_user_id, all_day_start, starts_at)",
        "CREATE INDEX ix_calendar_event_scopes_unit ON calendar_event_scopes(unit_id, event_id)",
        """
        CREATE FUNCTION reject_calendar_event_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'calendar events are cancelled, not deleted';
        END;
        $$ LANGUAGE plpgsql
        """,
        """
        CREATE TRIGGER trg_calendar_event_no_delete
        BEFORE DELETE ON calendar_events
        FOR EACH ROW EXECUTE FUNCTION reject_calendar_event_delete()
        """,
        """
        CREATE FUNCTION reject_calendar_history_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'calendar history is immutable';
        END;
        $$ LANGUAGE plpgsql
        """,
        """
        CREATE TRIGGER trg_calendar_history_immutable
        BEFORE UPDATE OR DELETE ON calendar_event_versions
        FOR EACH ROW EXECUTE FUNCTION reject_calendar_history_mutation()
        """,
    )
