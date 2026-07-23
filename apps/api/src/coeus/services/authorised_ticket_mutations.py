"""Explicit authority-fenced ticket mutations for protected workflows."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from coeus.application.ports.tickets import TicketRepository
from coeus.application.ports.workflow_transaction import WorkflowTransactionPort
from coeus.core.errors import AppError
from coeus.domain.store import StoreProduct
from coeus.domain.tickets import TicketRecord
from coeus.domain.workflow_authority import (
    WorkflowCommitAuthority,
    WorkflowCommitResult,
    WorkflowProductVisibility,
    workflow_authority_result,
)
from coeus.domain.workflow_transaction import WorkflowAuditIntent
from coeus.persistence.codec import decode_value
from coeus.persistence.state_store import StateStore
from coeus.services.audit import AuditLog

AuditEventInput = tuple[str, dict[str, str]]


class AuthorisedTicketMutations:
    _repository: TicketRepository
    _audit_log: AuditLog
    _transaction: WorkflowTransactionPort | None
    _state_store: StateStore | None

    def create_authorised_audited(
        self,
        proposed: TicketRecord,
        event_type: str,
        authority: WorkflowCommitAuthority,
        metadata: dict[str, str],
    ) -> TicketRecord:
        committed = replace(proposed, updated_at=datetime.now(UTC))
        audit = WorkflowAuditIntent(event_type, authority.expected_actor.user_id, metadata)
        if self._transaction is not None:
            result = self._transaction.commit_authorised_ticket_create(committed, audit, authority)
            _raise_workflow_conflict(result)
            self._accept_many((committed,))
            return committed
        self._guarded_create(
            committed,
            authority,
            lambda: self._audit_log.record(
                event_type, str(authority.expected_actor.user_id), metadata
            ),
        )
        return committed

    def save_authorised_audited_if_current(
        self,
        expected: TicketRecord,
        proposed: TicketRecord,
        event_type: str,
        authority: WorkflowCommitAuthority,
        metadata: dict[str, str],
        additional_events: tuple[AuditEventInput, ...] = (),
    ) -> TicketRecord:
        committed = replace(proposed, updated_at=datetime.now(UTC))
        events = ((event_type, metadata), *additional_events)
        audits = tuple(
            WorkflowAuditIntent(name, authority.expected_actor.user_id, event_metadata)
            for name, event_metadata in events
        )
        if self._transaction is not None:
            result = self._transaction.commit_authorised_ticket_update(
                expected, committed, audits, authority
            )
            _raise_workflow_conflict(result)
            self._accept_many((committed,))
            return committed
        return self._guarded_update(
            expected,
            committed,
            authority,
            lambda: self._audit_log.record_many(
                tuple(
                    (name, str(authority.expected_actor.user_id), event_metadata)
                    for name, event_metadata in events
                )
            ),
        )

    def save_authorised_if_current_with_confirmation(
        self,
        expected: TicketRecord,
        proposed: TicketRecord,
        authority: WorkflowCommitAuthority,
        confirm: Callable[[], object],
    ) -> TicketRecord:
        committed = replace(proposed, updated_at=datetime.now(UTC))
        return self._guarded_update(expected, committed, authority, confirm)

    def _guarded_create(
        self,
        committed: TicketRecord,
        authority: WorkflowCommitAuthority,
        confirm: Callable[[], object],
    ) -> None:
        if self._state_store is None:
            raise RuntimeError("Authorised ticket creates require an authority commit boundary.")
        state_store = self._state_store
        self._repository.save_with_guarded_confirmation(
            committed,
            lambda: _raise_workflow_conflict(_local_authority(state_store, authority)),
            confirm,
        )

    def _guarded_update(
        self,
        expected: TicketRecord,
        committed: TicketRecord,
        authority: WorkflowCommitAuthority,
        confirm: Callable[[], object],
    ) -> TicketRecord:
        if self._state_store is None:
            raise RuntimeError("Authorised ticket updates require an authority commit boundary.")
        state_store = self._state_store
        confirmed = self._repository.save_if_current_with_guarded_confirmation(
            expected,
            committed,
            lambda: _raise_workflow_conflict(_local_authority(state_store, authority)),
            confirm,
        )
        if not confirmed:
            raise _ticket_changed()
        return committed

    def _accept_many(self, tickets: tuple[TicketRecord, ...]) -> None:
        raise NotImplementedError


def _local_authority(
    state_store: StateStore, authority: WorkflowCommitAuthority
) -> WorkflowCommitResult:
    user_payload = state_store.load("users") or {}
    session_payload = state_store.load("sessions") or {}
    access_payload = state_store.load("access") or {}
    team_payload = state_store.load("teams") or {}
    store_payload = state_store.load("store") or {}
    users = tuple(decode_value(item) for item in user_payload.get("users", []))
    sessions = tuple(decode_value(item) for item in session_payload.get("sessions", []))
    acgs = tuple(decode_value(item) for item in access_payload.get("acgs", []))
    memberships = tuple(decode_value(item) for item in access_payload.get("memberships", []))
    teams = tuple(decode_value(item) for item in team_payload.get("items", []))
    products = tuple(
        _product_visibility(product)
        for item in store_payload.get("products", [])
        if isinstance((product := decode_value(item)), StoreProduct)
    )
    return workflow_authority_result(
        users,
        sessions,
        acgs,
        memberships,
        teams,
        products,
        authority,
    )


def _product_visibility(product: StoreProduct) -> WorkflowProductVisibility:
    return WorkflowProductVisibility(
        product.product_id,
        product.metadata.status,
        product.metadata.classification_level,
        product.metadata.acg_ids,
    )


def _raise_workflow_conflict(result: WorkflowCommitResult) -> None:
    if result is WorkflowCommitResult.COMMITTED:
        return
    if result is WorkflowCommitResult.TICKET_CHANGED:
        raise _ticket_changed()
    raise AppError(403, "forbidden", "Permission denied.")


def _ticket_changed() -> AppError:
    return AppError(
        409,
        "ticket_changed",
        "The ticket changed while the operation was running. Retry the operation.",
    )
