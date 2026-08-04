"""Real PostgreSQL evidence for safe legacy-calendar import."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from organisation_account_support import activate_analysts, activate_principals
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from coeus.domain.calendar_import import (
    CalendarImportCommand,
    CalendarImportConflict,
    candidate_from_legacy,
)
from coeus.domain.teams import CalendarStatus, OrgTeam, TeamCalendarEntry, TeamKind
from coeus.persistence.calendar_import_postgres import PostgresCalendarImportStore
from coeus.persistence.team_capacity_forecast_postgres import forecast_team_in_transaction
from coeus.repositories.teams import TeamRepository
from coeus.services.calendar_import import CalendarImportService

API_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.postgres


def _upgrade(database_url: str) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def _source(team: OrgTeam, entry: TeamCalendarEntry) -> TeamRepository:
    source = TeamRepository()
    source.save_team(team)
    source.save_entry(entry)
    return source


def _seed_workforce(engine, team_id, owner_id, creator_id):  # type: ignore[no-untyped-def]
    activate_analysts(engine, owner_id)
    activate_principals(engine, creator_id)
    now = datetime(2026, 8, 1, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organisation_units(unit_id,name,short_name,category,parent_unit_id,"
                "is_active,valid_from,valid_until,time_zone,description,provenance,version) "
                "VALUES (:unit_id,'Synthetic Import Team','SIT','delivery_team',NULL,true,"
                ":now,NULL,"
                "'Europe/London','','test',1)"
            ),
            {"unit_id": team_id, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO organisation_unit_closure(ancestor_unit_id,descendant_unit_id,depth) "
                "VALUES (:unit_id,:unit_id,0)"
            ),
            {"unit_id": team_id},
        )
        connection.execute(
            text(
                "INSERT INTO team_memberships(membership_id,user_id,unit_id,role,state,"
                "assignment_eligible,valid_from,valid_until,created_by_user_id,reason,provenance,"
                "version) VALUES (:membership_id,:owner_id,:unit_id,'member','active',true,"
                ":now,NULL,:creator_id,'Synthetic legacy import test','test',1)"
            ),
            {
                "membership_id": uuid4(),
                "owner_id": owner_id,
                "unit_id": team_id,
                "now": now,
                "creator_id": creator_id,
            },
        )
        connection.execute(
            text(
                "INSERT INTO working_patterns(pattern_id,user_id,time_zone,monday_minutes,"
                "tuesday_minutes,wednesday_minutes,thursday_minutes,friday_minutes,"
                "saturday_minutes,sunday_minutes,valid_from,valid_until,version,provenance,"
                "created_at,updated_at) VALUES (:pattern_id,:owner_id,'Europe/London',480,480,"
                "480,480,480,0,0,:now,NULL,1,'test',:now,:now)"
            ),
            {"pattern_id": uuid4(), "owner_id": owner_id, "now": now},
        )


def test_import_is_idempotent_private_and_changes_capacity_evidence(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    team_id, owner_id, creator_id = uuid4(), uuid4(), uuid4()
    _seed_workforce(engine, team_id, owner_id, creator_id)
    team = OrgTeam(team_id, "Synthetic Import Team", TeamKind.RFA)
    entry = TeamCalendarEntry(
        uuid4(),
        team_id,
        owner_id,
        "2026-08-10",
        CalendarStatus.LEAVE,
        "Sensitive synthetic medical detail.",
        "",
        creator_id,
        datetime(2026, 8, 2, 9, tzinfo=UTC),
    )
    service = CalendarImportService(_source(team, entry), PostgresCalendarImportStore(engine))
    actor_id = uuid4()
    start = datetime(2026, 8, 10, 8, tzinfo=UTC)
    end = datetime(2026, 8, 10, 16, tzinfo=UTC)
    with engine.begin() as connection:
        before = forecast_team_in_transaction(connection, team_id, start, end, start)
    preview = service.preview(actor_id)
    command_record = CalendarImportCommand(
        uuid4(), "legacy-calendar-import", actor_id, preview.preview_hash
    )
    result = service.apply(command_record)
    replay = service.apply(command_record)
    post_import_preview = service.preview(actor_id)
    with engine.begin() as connection:
        after = forecast_team_in_transaction(connection, team_id, start, end, start)
        row = (
            connection.execute(
                text(
                    "SELECT event.source,event.provenance,event.note,scope.unit_id "
                    "FROM calendar_events event JOIN calendar_event_scopes scope "
                    "ON scope.event_id=event.event_id"
                )
            )
            .mappings()
            .one()
        )
        evidence = " ".join(
            connection.execute(
                text(
                    "SELECT metadata::text FROM coeus_audit_events "
                    "WHERE event_type='legacy_calendar_imported' UNION ALL "
                    "SELECT payload::text FROM coeus_outbox "
                    "WHERE event_type='legacy_calendar_imported'"
                )
            ).scalars()
        )
    assert result.imported_count == 1 and replay.replayed
    assert post_import_preview.existing_count == 1
    assert post_import_preview.importable_count == 0
    assert before.unavailable_minutes == 0
    assert after.unavailable_minutes == 480 and after.assignable_minutes == 0
    assert row == {
        "source": "legacy",
        "provenance": "legacy_import",
        "note": "Sensitive synthetic medical detail.",
        "unit_id": team_id,
    }
    assert "Sensitive synthetic" not in evidence
    engine.dispose()


def test_collision_is_reported_and_import_evidence_is_immutable(
    postgres_database_url: str,
) -> None:
    _upgrade(postgres_database_url)
    engine = create_engine(postgres_database_url)
    team_id, owner_id, creator_id = uuid4(), uuid4(), uuid4()
    _seed_workforce(engine, team_id, owner_id, creator_id)
    team = OrgTeam(team_id, "Synthetic Import Team", TeamKind.RFA)
    entry = TeamCalendarEntry(
        uuid4(),
        team_id,
        owner_id,
        "2026-08-10",
        CalendarStatus.DUTY,
        "",
        "",
        creator_id,
        datetime(2026, 8, 2, 9, tzinfo=UTC),
    )
    service = CalendarImportService(_source(team, entry), PostgresCalendarImportStore(engine))
    stable = candidate_from_legacy(entry)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO calendar_events(event_id,owner_user_id,source,activity_category,"
                "all_day_start,all_day_end,time_zone,availability_effect,privacy_level,note,"
                "status,created_by_user_id,version,provenance) VALUES (:event_id,:owner_id,"
                "'legacy','duty','2026-08-10','2026-08-11','Europe/London','unavailable',"
                "'team_summary','','active',:creator_id,1,'collision')"
            ),
            {"event_id": stable.event_id, "owner_id": owner_id, "creator_id": creator_id},
        )
    actor_id = uuid4()
    blocked = service.preview(actor_id)
    assert any(item.code == "canonical_event_collision" for item in blocked.findings)
    with pytest.raises(CalendarImportConflict, match="blocking"):
        service.apply(CalendarImportCommand(uuid4(), "blocked", actor_id, blocked.preview_hash))
    evidence_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO calendar_import_commands(command_id,actor_user_id,idempotency_key,"
                "request_hash,preview_hash,source_digest,imported_count,existing_count,"
                "occurred_at) "
                "VALUES (:id,:id,'immutability',:digest,:digest,:digest,0,0,now())"
            ),
            {"id": evidence_id, "digest": "a" * 64},
        )
    with engine.begin() as connection, pytest.raises(DBAPIError, match="immutable"):
        connection.execute(
            text("DELETE FROM calendar_import_commands WHERE command_id=:id"), {"id": evidence_id}
        )
    engine.dispose()
