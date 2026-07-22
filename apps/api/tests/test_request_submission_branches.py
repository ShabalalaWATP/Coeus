from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.auth import AuthenticatedSession, RoleName, SessionRecord, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.services.request_submission import RequestSubmissionService


@pytest.mark.asyncio
async def test_submission_runs_active_work_after_a_definitive_no_match() -> None:
    actor = _actor()
    authenticated = _authenticated(actor)
    searching = _ticket(actor, TicketState.RFI_SEARCHING)
    consent = _ticket(actor, TicketState.NEW_TASKING_CONSENT, searching.ticket_id)
    discovered = _ticket(actor, TicketState.ACTIVE_WORK_REVIEW, searching.ticket_id)
    service, tickets, search, active = _service(searching)
    search.run.return_value = SimpleNamespace(ticket=consent)
    active.discover.return_value = discovered

    result = await service.submit(authenticated, searching.ticket_id)

    assert result is discovered
    tickets.tickets.submit.assert_called_once_with(actor, searching.ticket_id)
    active.discover.assert_called_once_with(authenticated, searching.ticket_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "state", "expected"),
    [
        (
            AppError(503, "provider_unavailable", "Unavailable"),
            TicketState.NEW_TASKING_CONSENT,
            "active",
        ),
        (RuntimeError("failed"), TicketState.DRAFT_INTAKE, "unchanged"),
        (RuntimeError("failed"), TicketState.RFI_SEARCHING, "incomplete"),
    ],
)
async def test_submission_failure_paths_are_explicit(
    error: Exception, state: TicketState, expected: str
) -> None:
    actor = _actor()
    authenticated = _authenticated(actor)
    submitted = _ticket(actor, TicketState.RFI_SEARCHING)
    visible = _ticket(actor, state, submitted.ticket_id)
    service, tickets, search, active = _service(submitted)
    search.run.side_effect = error
    tickets.tickets.get_visible_ticket.return_value = visible
    active.record_incomplete.return_value = visible

    result = await service.submit(authenticated, submitted.ticket_id)

    if expected == "active":
        active.record_incomplete.assert_called_once_with(
            authenticated, submitted.ticket_id, "provider_unavailable"
        )
    elif expected == "unchanged":
        assert result is visible
        tickets.mutations.save_authorised_audited_if_current.assert_not_called()
    else:
        assert result.state == TicketState.RFI_SEARCH_INCOMPLETE
        assert result.search_metrics[-1].degraded_reason == "search_failed"
        authority = tickets.mutations.save_authorised_audited_if_current.call_args.args[3]
        assert authority.expected_session == authenticated.session


@pytest.mark.asyncio
async def test_revoked_authority_in_failure_fallback_is_not_swallowed() -> None:
    actor = _actor()
    authenticated = _authenticated(actor)
    submitted = _ticket(actor, TicketState.RFI_SEARCHING)
    service, tickets, search, _active = _service(submitted)
    search.run.side_effect = RuntimeError("failed")
    tickets.tickets.get_visible_ticket.return_value = submitted
    tickets.mutations.save_authorised_audited_if_current.side_effect = AppError(
        403, "forbidden", "Permission denied."
    )

    with pytest.raises(AppError) as caught:
        await service.submit(authenticated, submitted.ticket_id)

    assert caught.value.code == "forbidden"


def _service(submitted: TicketRecord):
    tickets = SimpleNamespace(tickets=MagicMock(), mutations=MagicMock())
    tickets.tickets.submit.return_value = submitted
    tickets.mutations.save_authorised_audited_if_current.side_effect = (
        lambda _current, proposed, *_args: proposed
    )
    search = MagicMock()
    active = MagicMock()
    admission = MagicMock()
    admission.reserve.return_value = nullcontext()
    return (
        RequestSubmissionService(tickets, search, active, admission),
        tickets,
        search,
        active,
    )


def _actor() -> UserAccount:
    return UserAccount(
        uuid4(),
        "customer@example.test",
        "Synthetic Customer",
        frozenset({RoleName.USER}),
        frozenset(),
        "unused",
        True,
        2,
    )


def _ticket(actor: UserAccount, state: TicketState, ticket_id=None) -> TicketRecord:
    return TicketRecord(
        ticket_id=ticket_id or uuid4(),
        reference="RFI-SUBMISSION-BRANCH",
        requester_user_id=actor.user_id,
        state=state,
        intake=IntakeDetails(
            title="Synthetic request",
            operational_question="What changed?",
        ),
    )


def _authenticated(actor: UserAccount) -> AuthenticatedSession:
    session = SessionRecord(
        session_id="request-submission-session",
        user_id=actor.user_id,
        csrf_token="csrf",  # noqa: S106
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        created_at=datetime.now(UTC),
    )
    return AuthenticatedSession(session, actor)
