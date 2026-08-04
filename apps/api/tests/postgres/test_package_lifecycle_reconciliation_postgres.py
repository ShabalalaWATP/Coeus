"""Real PostgreSQL evidence for package and reservation lifecycle reconciliation."""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from coeus.domain.package_predecessor_cancellation import (
    CancelPredecessorCommand,
    DependantDisposition,
    DependantDispositionAction,
    PredecessorCancellationRequest,
)
from coeus.domain.work_package_contributors import (
    ChangeContributorCommand,
    ContributorCapacityPlan,
    ContributorOperation,
)
from coeus.persistence.package_predecessor_cancellation_postgres import (
    PostgresPredecessorCancellationStore,
)
from coeus.persistence.work_package_contributors_postgres import (
    PostgresWorkPackageContributorStore,
)
from postgres.package_lifecycle_support import (
    contributor_request,
    lifecycle_fixture,
)

pytestmark = pytest.mark.postgres


def test_contributor_capacity_is_reserved_and_released_atomically(
    postgres_database_url: str,
) -> None:
    evidence = lifecycle_fixture(postgres_database_url)
    engine = create_engine(postgres_database_url)
    store = PostgresWorkPackageContributorStore(engine)
    end_request = contributor_request(evidence, ContributorOperation.END, 1)
    end_preview = store.preview(evidence.actor_id, end_request)
    store.execute(
        ChangeContributorCommand(
            uuid4(),
            "end-target-contributor",
            evidence.actor_id,
            end_request,
            end_preview.preview_hash,
        )
    )
    with engine.connect() as connection:
        starts_at, ends_at = connection.execute(
            text("SELECT starts_at,ends_at FROM capacity_reservations LIMIT 1")
        ).one()
    plan = ContributorCapacityPlan(uuid4(), starts_at, ends_at, 60, "target-capacity")
    add_request = contributor_request(evidence, ContributorOperation.ADD, 2, plan)
    add_preview = store.preview(evidence.actor_id, add_request)
    added = store.execute(
        ChangeContributorCommand(
            uuid4(),
            "add-target-contributor",
            evidence.actor_id,
            add_request,
            add_preview.preview_hash,
        )
    )
    with engine.connect() as connection:
        reservation = connection.execute(
            text(
                "SELECT state,participant_role FROM capacity_reservations WHERE reservation_id=:id"
            ),
            {"id": plan.reservation_id},
        ).one()
    assert added.contributor_active and tuple(reservation) == ("active", "contributor")

    final_request = contributor_request(evidence, ContributorOperation.END, 3)
    final_preview = store.preview(evidence.actor_id, final_request)
    store.execute(
        ChangeContributorCommand(
            uuid4(),
            "release-target-contributor",
            evidence.actor_id,
            final_request,
            final_preview.preview_hash,
        )
    )
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT state FROM capacity_reservations WHERE reservation_id=:id"),
                {"id": plan.reservation_id},
            ).scalar_one()
            == "released"
        )
    engine.dispose()


def test_terminal_package_releases_reservations_and_participants(
    postgres_database_url: str,
) -> None:
    evidence = lifecycle_fixture(postgres_database_url)
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE canonical_work_packages SET state='cancelled',remaining_minutes=0,"
                "version=version+1 WHERE package_id=:id"
            ),
            {"id": evidence.package_id},
        )
    with engine.connect() as connection:
        states = tuple(
            connection.execute(
                text("SELECT DISTINCT state FROM capacity_reservations WHERE package_id=:id"),
                {"id": evidence.package_id},
            ).scalars()
        )
        active = connection.execute(
            text("SELECT count(*) FROM work_package_participants WHERE package_id=:id AND active"),
            {"id": evidence.package_id},
        ).scalar_one()
    assert states == ("released",) and active == 0

    engine.dispose()


def test_account_suspension_and_calendar_change_reconcile(
    postgres_database_url: str,
) -> None:
    evidence = lifecycle_fixture(postgres_database_url)
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        reservation = connection.execute(
            text("SELECT starts_at,ends_at FROM capacity_reservations WHERE reservation_id=:id"),
            {"id": evidence.contributor_reservation_id},
        ).one()
        connection.execute(
            text(
                "INSERT INTO calendar_events(event_id,owner_user_id,source,activity_category,"
                "starts_at,ends_at,time_zone,availability_effect,privacy_level,note,status,"
                "created_by_user_id) VALUES (:event,:owner,'personal','leave',:start,:end,"
                "'Europe/London','unavailable','private','','active',:owner)"
            ),
            {
                "event": uuid4(),
                "owner": evidence.contributor_id,
                "start": reservation[0],
                "end": reservation[1],
            },
        )
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=false WHERE user_id=:id"),
            {"id": evidence.target_id},
        )
        connection.execute(
            text(
                "INSERT INTO identity_account_projection"
                "(user_id,is_active,roles,credential_version,source_hash) "
                "VALUES (:id,true,ARRAY['Analyst'],1,:hash)"
            ),
            {"id": evidence.owner_id, "hash": "d" * 64},
        )
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=false WHERE user_id=:id"),
            {"id": evidence.owner_id},
        )
    with engine.connect() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT active FROM work_package_participants WHERE package_id=:package "
                    "AND user_id=:user AND role='contributor'"
                ),
                {"package": evidence.package_id, "user": evidence.target_id},
            ).scalar_one()
            is False
        )
        reasons = set(
            connection.execute(
                text(
                    "SELECT reason_code FROM package_lifecycle_conflicts WHERE package_id=:package"
                ),
                {"package": evidence.package_id},
            ).scalars()
        )
        package_state = connection.execute(
            text(
                "SELECT state,accountable_user_id FROM canonical_work_packages "
                "WHERE package_id=:package"
            ),
            {"package": evidence.package_id},
        ).one()
    assert {"calendar_reforecast_required", "account_ineligible"} <= reasons
    assert tuple(package_state) == ("pending", None)
    engine.dispose()


def test_explicit_unlink_disposition_cancels_predecessor(postgres_database_url: str) -> None:
    evidence = lifecycle_fixture(postgres_database_url)
    engine = create_engine(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE canonical_work_packages SET state='ready',remaining_minutes=120,version=2 "
                "WHERE package_id=:id"
            ),
            {"id": evidence.predecessor_id},
        )
    request = PredecessorCancellationRequest(
        evidence.unit_id,
        evidence.predecessor_id,
        2,
        2,
        evidence.request.authorising_grant_id,
        evidence.request.expected_grant_version,
        (DependantDisposition(evidence.package_id, 1, DependantDispositionAction.UNLINK),),
    )
    store = PostgresPredecessorCancellationStore(engine)
    preview = store.preview(evidence.actor_id, request)
    result = store.execute(
        CancelPredecessorCommand(
            uuid4(), "cancel-predecessor", evidence.actor_id, request, preview.preview_hash
        )
    )
    with engine.connect() as connection:
        edge_count = connection.execute(
            text("SELECT count(*) FROM work_package_dependencies WHERE predecessor_package_id=:id"),
            {"id": evidence.predecessor_id},
        ).scalar_one()
    assert (result.package_version, result.unlinked_dependants, edge_count) == (3, 1, 0)
    engine.dispose()
