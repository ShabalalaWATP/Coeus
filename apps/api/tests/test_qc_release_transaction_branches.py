"""Hosted QC release result mapping and cache acceptance branches."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.auth import AuthenticatedSession, RoleName, SessionRecord, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.product_submission import DraftProductVersion
from coeus.domain.store import StoreProduct, StoreProductMetadata
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.domain.workflow_authority import WorkflowCommitResult
from coeus.services.audit import AuditLog
from coeus.services.qc_release import QcReleaseStep


class _QcTransaction:
    def __init__(self, result: WorkflowCommitResult) -> None:
        self.result = result
        self.committed: TicketRecord | None = None

    def commit_authorised_qc_release(self, *args: object) -> WorkflowCommitResult:
        self.committed = args[1]  # type: ignore[assignment]
        return self.result


@pytest.mark.parametrize(
    ("result", "expected_code"),
    [
        (WorkflowCommitResult.AUTHORITY_REVOKED, "forbidden"),
        (WorkflowCommitResult.TICKET_CHANGED, "ticket_changed"),
    ],
)
def test_hosted_qc_release_maps_authority_and_ticket_conflicts(
    result: WorkflowCommitResult,
    expected_code: str,
) -> None:
    step, authenticated, ticket, product = _release_step(result)

    with pytest.raises(AppError) as caught:
        step._commit_or_save(
            authenticated,
            ticket,
            replace(ticket, state=TicketState.DISSEMINATION_READY),
            product,
            "product_released",
            None,
            None,
        )

    assert caught.value.code == expected_code


def test_hosted_qc_release_accepts_committed_caches() -> None:
    step, authenticated, ticket, product = _release_step(WorkflowCommitResult.COMMITTED)

    committed = step._commit_or_save(
        authenticated,
        ticket,
        replace(ticket, state=TicketState.DISSEMINATION_READY),
        product,
        "product_released",
        None,
        None,
    )

    assert committed.state is TicketState.DISSEMINATION_READY
    step._tickets.tickets.accept_committed_system_update.assert_called_once_with(committed)
    step._store.repository.accept_committed.assert_called_once_with(product)


def _release_step(
    result: WorkflowCommitResult,
) -> tuple[QcReleaseStep, AuthenticatedSession, TicketRecord, StoreProduct]:
    actor = _actor()
    authenticated = AuthenticatedSession(
        SessionRecord(
            "qc-branch-session",
            actor.user_id,
            "qc-branch-csrf",
            datetime.now(UTC) + timedelta(hours=1),
            datetime.now(UTC),
        ),
        actor,
    )
    ticket = _ticket(actor)
    product = _product(actor)
    tickets = SimpleNamespace(tickets=MagicMock(), mutations=MagicMock())
    store = SimpleNamespace(repository=MagicMock(), details=MagicMock())
    transaction = _QcTransaction(result)
    step = QcReleaseStep(
        tickets,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        MagicMock(),
        MagicMock(),
        AuditLog(),
        transaction,  # type: ignore[arg-type]
    )
    return step, authenticated, ticket, product


def _actor() -> UserAccount:
    return UserAccount(
        uuid4(),
        "qc-branch@example.test",
        "QC Branch",
        frozenset({RoleName.QUALITY_CONTROL_MANAGER}),
        frozenset({Permission.QC_APPROVE}),
        "synthetic-hash",
        True,
        3,
    )


def _ticket(actor: UserAccount) -> TicketRecord:
    ticket_id = uuid4()
    draft = DraftProductVersion(
        uuid4(),
        ticket_id,
        1,
        "Synthetic draft",
        "Synthetic summary",
        "assessment",
        "Synthetic content",
        (),
        uuid4(),
        datetime.now(UTC),
    )
    return TicketRecord(
        ticket_id=ticket_id,
        reference="TCK-QC-BRANCH",
        requester_user_id=actor.user_id,
        state=TicketState.QC_REVIEW,
        intake=IntakeDetails(title="Synthetic QC branch"),
        draft_products=(draft,),
    )


def _product(actor: UserAccount) -> StoreProduct:
    now = datetime.now(UTC)
    return StoreProduct(
        uuid4(),
        "PROD-QC-BRANCH",
        StoreProductMetadata(
            title="Synthetic QC product",
            summary="Synthetic summary",
            description="Synthetic description",
            product_type="assessment",
            source_type="synthetic",
            owner_team="QC",
            area_or_region="Synthetic region",
            classification_level=1,
            releasability=frozenset({"MOCK"}),
            handling_caveats=frozenset({"MOCK DATA ONLY"}),
            tags=frozenset({"synthetic"}),
            acg_ids=frozenset({uuid4()}),
            status=ProductStatus.PUBLISHED,
            time_period_start=None,
            time_period_end=None,
            geojson_ref=None,
            bounding_box=None,
        ),
        (),
        actor.user_id,
        now,
        now,
    )
