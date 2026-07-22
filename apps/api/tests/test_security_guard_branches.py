from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from coeus.application.ports.access import ActiveAcgReader
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.customer_outcomes import (
    CustomerProductDecision,
    CustomerProductDecisionStatus,
    ManagerReanalysisDecision,
    ManagerReanalysisStatus,
    ProductOutcomeHistory,
)
from coeus.domain.enums import TicketState
from coeus.domain.product_submission import DraftProductAsset, DraftProductVersion
from coeus.domain.tickets import (
    IntakeDetails,
    ManagerRoutingDecisionStatus,
    ProductDissemination,
    RoutingRoute,
    TicketRecord,
)
from coeus.repositories.teams import TeamRepository
from coeus.services.analyst_records import assignment_record
from coeus.services.customer_outcomes import CustomerOutcomeService, _require_transition
from coeus.services.object_storage import ObjectStorage
from coeus.services.routing_records import decision as routing_decision
from coeus.services.tickets import TicketServices
from coeus.services.workflow_draft_access import (
    WorkflowDraftAccessPolicy,
    WorkflowDraftAccessService,
)


class _TicketReader:
    def __init__(self, ticket: TicketRecord) -> None:
        self.ticket = ticket

    def get_visible_ticket(self, _actor: UserAccount, _ticket_id: UUID) -> TicketRecord:
        return self.ticket

    def get_workflow_ticket(
        self, _actor: UserAccount, _ticket_id: UUID, _permissions: frozenset[Permission]
    ) -> TicketRecord:
        return self.ticket


class _AcgReader:
    def active_acg_ids_for_user(self, _user_id: UUID) -> frozenset[UUID]:
        return frozenset()


class _Storage:
    def __init__(self, content: bytes = b"", *, exists: bool = False) -> None:
        self.content = content
        self.available = exists

    def exists(self, _object_key: str) -> bool:
        return self.available

    def read_bytes(self, _object_key: str) -> bytes:
        return self.content


def test_customer_outcome_guards_fail_closed_at_each_decision_boundary() -> None:
    owner = _actor({Permission.TICKET_READ_OWN})
    outsider = _actor({Permission.TICKET_READ_OWN})
    ticket = _released_ticket(owner.user_id)
    reader = _TicketReader(ticket)
    service = CustomerOutcomeService(_ticket_services(reader))

    _assert_error(
        "forbidden",
        lambda: service.customer_decision(
            outsider, ticket.ticket_id, meets_requirement=True, reason="Accepted", unmet_criteria=()
        ),
    )
    _assert_error(
        "reason_required",
        lambda: service.customer_decision(
            owner, ticket.ticket_id, meets_requirement=False, reason=" ", unmet_criteria=()
        ),
    )

    manager = _actor({Permission.RFA_REVIEW})
    _assert_error(
        "reason_required",
        lambda: service.manager_decision(manager, ticket.ticket_id, agree=True, rationale=" "),
    )
    _assert_error(
        "invalid_ticket_state",
        lambda: service.manager_decision(manager, ticket.ticket_id, agree=True, rationale="Valid"),
    )

    reader.ticket = replace(ticket, state=TicketState.MANAGER_REANALYSIS_REVIEW)
    _assert_error(
        "forbidden",
        lambda: service.manager_decision(manager, ticket.ticket_id, agree=True, rationale="Valid"),
    )
    routed = _with_route(reader.ticket, owner.user_id)
    reader.ticket = replace(
        routed,
        analyst_assignments=(
            assignment_record(routed.ticket_id, manager.user_id, owner.user_id, RoutingRoute.RFA),
        ),
        product_outcomes=ProductOutcomeHistory(customer_decisions=(_customer_decision(routed),)),
    )
    _assert_error(
        "separation_of_duties",
        lambda: service.manager_decision(manager, ticket.ticket_id, agree=True, rationale="Valid"),
    )
    reader.ticket = replace(routed, product_outcomes=ProductOutcomeHistory())
    _assert_error(
        "decision_context_missing",
        lambda: service.manager_decision(manager, ticket.ticket_id, agree=True, rationale="Valid"),
    )

    jioc = _actor({Permission.JIOC_RESOLVE_CUSTOMER_DISPUTE})
    _assert_error(
        "forbidden",
        lambda: service.jioc_decision(
            outsider, ticket.ticket_id, reanalyse=True, rationale="Valid"
        ),
    )
    _assert_error(
        "reason_required",
        lambda: service.jioc_decision(jioc, ticket.ticket_id, reanalyse=True, rationale=" "),
    )
    _assert_error(
        "invalid_ticket_state",
        lambda: service.jioc_decision(jioc, ticket.ticket_id, reanalyse=True, rationale="Valid"),
    )
    customer = _customer_decision(routed)
    reader.ticket = replace(
        routed,
        state=TicketState.JIOC_REANALYSIS_ADJUDICATION,
        product_outcomes=ProductOutcomeHistory(customer_decisions=(customer,)),
    )
    _assert_error(
        "decision_context_missing",
        lambda: service.jioc_decision(jioc, ticket.ticket_id, reanalyse=True, rationale="Valid"),
    )
    manager_outcome = ManagerReanalysisDecision(
        uuid4(),
        routed.ticket_id,
        customer.decision_id,
        ManagerReanalysisStatus.REFERRED_TO_JIOC,
        "Refer",
        manager.user_id,
        datetime.now(UTC),
    )
    reader.ticket = replace(
        reader.ticket,
        requester_user_id=jioc.user_id,
        product_outcomes=replace(
            reader.ticket.product_outcomes, manager_decisions=(manager_outcome,)
        ),
    )
    _assert_error(
        "separation_of_duties",
        lambda: service.jioc_decision(jioc, ticket.ticket_id, reanalyse=True, rationale="Valid"),
    )
    _assert_error(
        "invalid_ticket_state",
        lambda: _require_transition(reader.ticket, TicketState.QC_REVIEW),
    )


def test_workflow_draft_preview_enforces_live_object_and_integrity_guards() -> None:
    actor = _actor({Permission.PRODUCT_READ, Permission.QC_REVIEW})
    actor.roles = frozenset({RoleName.QUALITY_CONTROL_MANAGER})
    content = b"synthetic draft"
    asset = DraftProductAsset(
        uuid4(),
        "draft.pdf",
        "pdf",
        "application/pdf",
        len(content),
        sha256(content).hexdigest(),
        object_key="drafts/example.pdf",
    )
    version = DraftProductVersion(
        uuid4(),
        uuid4(),
        1,
        "Draft",
        "Synthetic summary",
        "assessment",
        "Synthetic content",
        (asset,),
        uuid4(),
        datetime.now(UTC),
    )
    ticket = TicketRecord(
        version.ticket_id,
        "RFI-DRAFT-GUARDS",
        uuid4(),
        TicketState.QC_REVIEW,
        IntakeDetails(),
        draft_products=(version,),
        qc_reviewer_user_id=actor.user_id,
    )
    policy = WorkflowDraftAccessPolicy(
        cast(ActiveAcgReader, _AcgReader()), cast(TeamRepository, SimpleNamespace())
    )

    unauthorised = _actor(set())
    _assert_error(
        "submission_not_found", lambda: policy.require_version(unauthorised, ticket, version)
    )
    unassigned = _actor({Permission.PRODUCT_READ})
    manager_state = replace(ticket, state=TicketState.MANAGER_APPROVAL, qc_reviewer_user_id=None)
    _assert_error(
        "submission_not_found",
        lambda: policy.require_version(unassigned, manager_state, version),
    )

    reader = _TicketReader(ticket)
    missing_storage = _Storage()
    previews = WorkflowDraftAccessService(
        _ticket_services(reader), policy, cast(ObjectStorage, missing_storage)
    )
    _assert_error(
        "submission_not_found",
        lambda: previews.preview(actor, ticket.ticket_id, uuid4(), asset.asset_id),
    )
    _assert_error(
        "submission_not_found",
        lambda: previews.preview(actor, ticket.ticket_id, version.version_id, asset.asset_id),
    )
    corrupt = _Storage(b"tampered", exists=True)
    previews = WorkflowDraftAccessService(
        _ticket_services(reader), policy, cast(ObjectStorage, corrupt)
    )
    _assert_error(
        "submission_asset_integrity_failed",
        lambda: previews.preview(actor, ticket.ticket_id, version.version_id, asset.asset_id),
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


def _released_ticket(owner_id: UUID) -> TicketRecord:
    ticket_id = uuid4()
    return TicketRecord(
        ticket_id,
        "RFI-OUTCOME-GUARDS",
        owner_id,
        TicketState.DISSEMINATION_READY,
        IntakeDetails(),
        disseminations=(
            ProductDissemination(uuid4(), ticket_id, uuid4(), owner_id, datetime.now(UTC)),
        ),
    )


def _with_route(ticket: TicketRecord, actor_id: UUID) -> TicketRecord:
    return replace(
        ticket,
        manager_decisions=(
            routing_decision(
                ticket.ticket_id,
                actor_id,
                RoutingRoute.RFA,
                ManagerRoutingDecisionStatus.APPROVED,
                "Approved",
                None,
            ),
        ),
    )


def _customer_decision(ticket: TicketRecord) -> CustomerProductDecision:
    return CustomerProductDecision(
        uuid4(),
        ticket.ticket_id,
        uuid4(),
        CustomerProductDecisionStatus.REJECTED,
        "Synthetic requirement gap",
        ("Synthetic criterion",),
        ticket.requester_user_id,
        datetime.now(UTC),
    )


def _ticket_services(reader: _TicketReader) -> TicketServices:
    return cast(
        TicketServices,
        SimpleNamespace(
            tickets=reader,
            mutations=SimpleNamespace(),
        ),
    )


def _assert_error(code: str, action: Callable[[], object]) -> None:
    with pytest.raises(AppError) as raised:
        action()
    assert raised.value.code == code
