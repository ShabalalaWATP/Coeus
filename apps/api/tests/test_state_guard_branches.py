from collections.abc import Callable
from dataclasses import replace
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.repositories.access import AccessRepository
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.analyst_workflow import AnalystWorkflowService
from coeus.services.audit import AuditLog
from coeus.services.intake import RequirementCompletenessService
from coeus.services.object_storage import ObjectStorage
from coeus.services.product_submissions import ProductSubmissionService, _validate_dates
from coeus.services.tickets import TicketService, TicketServices


def test_upload_and_ticket_state_guards_cover_denial_paths() -> None:
    ticket = TicketRecord(
        uuid4(), "RFI-UPLOAD-GUARD", uuid4(), TicketState.CANCELLED, IntakeDetails()
    )
    analyst = SimpleNamespace(task_details=lambda _actor, _ticket_id: ticket)
    submissions = ProductSubmissionService(
        cast(TicketServices, SimpleNamespace()),
        cast(AnalystWorkflowService, analyst),
        cast(AccessRepository, SimpleNamespace()),
        cast(ObjectStorage, SimpleNamespace()),
        Settings(environment="test", argon2_memory_cost=8_192),
    )
    denied = _actor(set())
    _assert_error("forbidden", lambda: submissions.authorise_upload(denied, ticket.ticket_id))
    analyst_actor = _actor({Permission.ANALYST_SUBMIT_PRODUCT})
    _assert_error(
        "invalid_ticket_state",
        lambda: submissions.authorise_upload(analyst_actor, ticket.ticket_id),
    )
    _assert_error("product_dates_invalid", lambda: _validate_dates("2026-02-01", "2026-01-01"))

    repository = InMemoryTicketRepository()
    service = TicketService(repository, RequirementCompletenessService(), AuditLog())
    customer = _actor({Permission.TICKET_READ_OWN})
    stored = replace(ticket, requester_user_id=customer.user_id)
    repository.save(stored)
    assert service.list_workflow_tickets(customer, frozenset({Permission.RFA_REVIEW})) == ()
    _assert_error(
        "ticket_not_found",
        lambda: service.get_workflow_ticket(
            customer, stored.ticket_id, frozenset({Permission.RFA_REVIEW})
        ),
    )
    _assert_error("ticket_not_editable", lambda: service.submit(customer, stored.ticket_id))

    complete = IntakeDetails(
        title="Synthetic request",
        description="Synthetic need",
        operational_question="What changed?",
        area_or_region="Synthetic region",
        time_period_start="2026-01-01",
        time_period_end="2026-02-01",
        priority="routine",
        deadline="2026-03-01",
        required_output_format="Assessment",
        known_context="Synthetic context",
        restrictions_or_caveats="None",
        customer_success_criteria="Answers the question",
        suggested_acg_context="Synthetic ACG",
        requesting_unit="Synthetic unit",
        intelligence_disciplines="All-source",
        supported_operation="Synthetic exercise",
    )
    info_required = replace(
        stored, ticket_id=uuid4(), state=TicketState.INFO_REQUIRED, intake=complete
    )
    repository.save(info_required)
    _assert_error("invalid_ticket_state", lambda: service.submit(customer, info_required.ticket_id))
    assert service.state_for_intake(TicketState.CLOSED_REQUIREMENT_MET, complete) == (
        TicketState.CLOSED_REQUIREMENT_MET
    )


def _actor(permissions: set[Permission]) -> UserAccount:
    return UserAccount(
        uuid4(),
        f"user-{uuid4()}@example.test",
        "Synthetic User",
        frozenset(),
        frozenset(permissions),
        "hash",
        True,
        5,
    )


def _assert_error(code: str, action: Callable[[], object]) -> None:
    with pytest.raises(AppError) as raised:
        action()
    assert raised.value.code == code
