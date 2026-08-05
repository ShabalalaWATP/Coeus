"""Target-account and posting evidence re-checked during a handover."""

from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from work_package_handover_support import insert_handover_evidence, upgrade_handover_schema

from coeus.domain.work_package_handovers import WorkPackageHandoverDenied
from coeus.persistence.work_package_handovers_postgres import PostgresWorkPackageHandoverStore

pytestmark = pytest.mark.postgres


def _evidence(database_url: str):  # type: ignore[no-untyped-def]
    upgrade_handover_schema(database_url)
    evidence = insert_handover_evidence(database_url)
    return create_engine(database_url), evidence


def test_a_package_outside_the_named_unit_is_unavailable(postgres_database_url: str) -> None:
    engine, evidence = _evidence(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)

    with pytest.raises(WorkPackageHandoverDenied, match="work package is unavailable"):
        store.preview(evidence.actor_id, replace(evidence.request, unit_id=uuid4()))
    engine.dispose()


@pytest.mark.parametrize(
    "field",
    ["expected_target_account_credential_version", "expected_target_account_source_hash"],
)
def test_stale_target_account_evidence_is_refused(postgres_database_url: str, field: str) -> None:
    engine, evidence = _evidence(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)
    value = 99 if field.endswith("version") else "d" * 64

    with pytest.raises(WorkPackageHandoverDenied, match="target account evidence"):
        store.preview(evidence.actor_id, replace(evidence.request, **{field: value}))
    engine.dispose()


def test_a_suspended_target_cannot_receive_the_package(postgres_database_url: str) -> None:
    engine, evidence = _evidence(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=false WHERE user_id=:user"),
            {"user": evidence.request.target_user_id},
        )
    store = PostgresWorkPackageHandoverStore(engine)

    with pytest.raises(WorkPackageHandoverDenied, match="target account evidence"):
        store.preview(evidence.actor_id, evidence.request)
    engine.dispose()


@pytest.mark.parametrize("field", ["target_membership_id", "expected_target_membership_version"])
def test_stale_target_posting_evidence_is_refused(postgres_database_url: str, field: str) -> None:
    engine, evidence = _evidence(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)
    value = uuid4() if field == "target_membership_id" else 99

    with pytest.raises(WorkPackageHandoverDenied, match="target home-posting evidence"):
        store.preview(evidence.actor_id, replace(evidence.request, **{field: value}))
    engine.dispose()


def test_a_target_without_an_eligible_posting_is_refused(postgres_database_url: str) -> None:
    engine, evidence = _evidence(postgres_database_url)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE team_memberships SET assignment_eligible=false WHERE user_id=:user"),
            {"user": evidence.request.target_user_id},
        )
    store = PostgresWorkPackageHandoverStore(engine)

    with pytest.raises(WorkPackageHandoverDenied, match="one eligible posting"):
        store.preview(evidence.actor_id, evidence.request)
    engine.dispose()


@pytest.mark.parametrize("field", ["expected_ticket_version", "expected_ticket_source_hash"])
def test_stale_ticket_evidence_makes_the_package_unavailable(
    postgres_database_url: str, field: str
) -> None:
    engine, evidence = _evidence(postgres_database_url)
    store = PostgresWorkPackageHandoverStore(engine)
    value = 99 if field.endswith("version") else "c" * 64

    with pytest.raises(WorkPackageHandoverDenied, match="work package is unavailable"):
        store.preview(evidence.actor_id, replace(evidence.request, **{field: value}))
    engine.dispose()
