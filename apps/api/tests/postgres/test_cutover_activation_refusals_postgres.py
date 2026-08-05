"""Separation-of-duties and immutability refusals during cutover activation."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_cutover_activation_postgres import NOW, _manifest, _migrate_and_seed

from coeus.domain.cutover_activation import CutoverApprovalRole, CutoverSlice

pytestmark = pytest.mark.postgres


def test_a_second_preview_of_the_same_slice_is_refused(postgres_database_url: str) -> None:
    store, actors = _migrate_and_seed(postgres_database_url)
    store.preview(CutoverSlice.CALENDAR, _manifest(), actors[0], NOW)

    with pytest.raises(ValueError, match="already has an immutable preview"):
        store.preview(CutoverSlice.CALENDAR, _manifest(), actors[0], NOW + timedelta(minutes=1))


def test_another_candidate_cannot_bind_while_one_is_recorded(
    postgres_database_url: str,
) -> None:
    store, actors = _migrate_and_seed(postgres_database_url)
    store.preview(CutoverSlice.CALENDAR, _manifest(), actors[0], NOW)
    other = _manifest()
    object.__setattr__(other, "source_revision", "fedcba654321")

    with pytest.raises(ValueError, match="another exact cutover candidate"):
        store.preview(CutoverSlice.ORGANISATION, other, actors[0], NOW + timedelta(minutes=1))


def test_a_proposer_may_not_approve_their_own_candidate(postgres_database_url: str) -> None:
    store, actors = _migrate_and_seed(postgres_database_url)
    preview = store.preview(CutoverSlice.CALENDAR, _manifest(), actors[0], NOW)

    with pytest.raises(PermissionError, match="cannot approve their own candidate"):
        store.approve(
            CutoverSlice.CALENDAR,
            preview.candidate_hash,
            preview.preview_hash,
            CutoverApprovalRole.SECURITY_REVIEW,
            actors[0],
            NOW + timedelta(seconds=1),
        )


def test_one_person_cannot_hold_both_approval_roles(postgres_database_url: str) -> None:
    store, actors = _migrate_and_seed(postgres_database_url)
    preview = store.preview(CutoverSlice.CALENDAR, _manifest(), actors[0], NOW)
    store.approve(
        CutoverSlice.CALENDAR,
        preview.candidate_hash,
        preview.preview_hash,
        CutoverApprovalRole.SECURITY_REVIEW,
        actors[1],
        NOW + timedelta(seconds=1),
    )

    with pytest.raises(PermissionError, match="require distinct people"):
        store.approve(
            CutoverSlice.CALENDAR,
            preview.candidate_hash,
            preview.preview_hash,
            CutoverApprovalRole.RELEASE_AUTHORITY,
            actors[1],
            NOW + timedelta(seconds=2),
        )


def test_an_approval_role_is_recorded_once(postgres_database_url: str) -> None:
    store, actors = _migrate_and_seed(postgres_database_url)
    preview = store.preview(CutoverSlice.CALENDAR, _manifest(), actors[0], NOW)
    store.approve(
        CutoverSlice.CALENDAR,
        preview.candidate_hash,
        preview.preview_hash,
        CutoverApprovalRole.SECURITY_REVIEW,
        actors[1],
        NOW + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="already has immutable evidence"):
        store.approve(
            CutoverSlice.CALENDAR,
            preview.candidate_hash,
            preview.preview_hash,
            CutoverApprovalRole.SECURITY_REVIEW,
            actors[2],
            NOW + timedelta(seconds=2),
        )


@pytest.mark.parametrize("field", ["candidate", "preview"])
def test_an_unknown_candidate_or_preview_cannot_be_approved(
    postgres_database_url: str, field: str
) -> None:
    store, actors = _migrate_and_seed(postgres_database_url)
    preview = store.preview(CutoverSlice.CALENDAR, _manifest(), actors[0], NOW)

    with pytest.raises(ValueError, match="missing, stale or expired"):
        store.approve(
            CutoverSlice.CALENDAR,
            "9" * 64 if field == "candidate" else preview.candidate_hash,
            "9" * 64 if field == "preview" else preview.preview_hash,
            CutoverApprovalRole.SECURITY_REVIEW,
            actors[1],
            NOW + timedelta(seconds=1),
        )


def test_a_lapsed_preview_cannot_be_approved(postgres_database_url: str) -> None:
    store, actors = _migrate_and_seed(postgres_database_url)
    preview = store.preview(CutoverSlice.CALENDAR, _manifest(), actors[0], NOW)

    with pytest.raises(ValueError, match="missing, stale or expired"):
        store.approve(
            CutoverSlice.CALENDAR,
            preview.candidate_hash,
            preview.preview_hash,
            CutoverApprovalRole.SECURITY_REVIEW,
            actors[1],
            preview.expires_at + timedelta(seconds=1),
        )


def test_only_an_active_administrator_may_preview_or_approve(
    postgres_database_url: str,
) -> None:
    store, actors = _migrate_and_seed(postgres_database_url)
    stranger = uuid4()

    with pytest.raises(PermissionError, match="active human administrator"):
        store.preview(CutoverSlice.CALENDAR, _manifest(), stranger, NOW)

    preview = store.preview(CutoverSlice.CALENDAR, _manifest(), actors[0], NOW)
    with store._engine.begin() as connection:  # type: ignore[attr-defined]
        connection.execute(
            text("UPDATE identity_account_projection SET is_active=false WHERE user_id=:actor"),
            {"actor": actors[1]},
        )
    with pytest.raises(PermissionError, match="active human administrator"):
        store.approve(
            CutoverSlice.CALENDAR,
            preview.candidate_hash,
            preview.preview_hash,
            CutoverApprovalRole.SECURITY_REVIEW,
            actors[1],
            NOW + timedelta(seconds=1),
        )


def test_a_recorded_candidate_reports_its_own_ineligibility(
    postgres_database_url: str,
) -> None:
    store, actors = _migrate_and_seed(postgres_database_url)

    assert not store.state().eligible
    store.preview(CutoverSlice.CALENDAR, _manifest(), actors[0], NOW)
    state = store.state()

    assert state.candidate_hash == _manifest().candidate_hash
    assert not state.eligible
