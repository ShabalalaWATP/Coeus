from dataclasses import replace
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.enums import TicketState
from coeus.domain.store import StoreProduct
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.domain.workflow_transaction import ReleaseNotificationIntent, WorkflowAuditIntent
from coeus.persistence.audit_store import MemoryAuditEventStore
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.audit import AuditLog
from coeus.services.ticket_mutations import TicketMutationService


class StubWorkflowTransaction:
    def __init__(self) -> None:
        self.create_result = True
        self.update_result = True
        self.pair_result = True
        self.created: TicketRecord | None = None
        self.updated: TicketRecord | None = None
        self.paired: tuple[TicketRecord, TicketRecord] | None = None

    def commit_ticket_create(
        self, ticket: TicketRecord, _audit: WorkflowAuditIntent
    ) -> bool:
        self.created = ticket
        return self.create_result

    def commit_ticket_update(
        self,
        _expected: TicketRecord,
        updated: TicketRecord,
        _audits: tuple[WorkflowAuditIntent, ...],
    ) -> bool:
        self.updated = updated
        return self.update_result

    def commit_ticket_pair(
        self,
        _expected: tuple[TicketRecord, TicketRecord],
        updated: tuple[TicketRecord, TicketRecord],
        _audits: tuple[WorkflowAuditIntent, ...],
    ) -> bool:
        self.paired = updated
        return self.pair_result

    def commit_qc_release(
        self,
        _expected: TicketRecord,
        _updated: TicketRecord,
        _product: StoreProduct,
        _audit: WorkflowAuditIntent,
        _notification: ReleaseNotificationIntent | None,
    ) -> bool:
        return True


class RejectBatchAuditStore(MemoryAuditEventStore):
    def append_many(self, _events: tuple[dict[str, object], ...]) -> None:
        raise RuntimeError("audit batch")


def _raise_oserror(*_args: object) -> None:
    raise OSError("synthetic cache failure")


def _ticket(reference: str = "TCK-MUTATION-0001") -> TicketRecord:
    return TicketRecord(
        ticket_id=uuid4(),
        reference=reference,
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Synthetic mutation test"),
    )


def _seed_pair() -> tuple[InMemoryTicketRepository, TicketRecord, TicketRecord]:
    repository = InMemoryTicketRepository()
    first = _ticket("TCK-MUTATION-0001")
    second = _ticket("TCK-MUTATION-0002")
    repository.save(first)
    repository.save(second)
    return repository, first, second


def test_workflow_audit_intent_metadata_is_an_immutable_snapshot() -> None:
    metadata = {"decision": "allow"}
    intent = WorkflowAuditIntent("decision", uuid4(), metadata)
    metadata["decision"] = "deny"

    assert dict(intent.metadata) == {"decision": "allow"}
    with pytest.raises(TypeError):
        intent.metadata["decision"] = "changed"  # type: ignore[index]


def test_compatibility_create_and_basic_persistence_helpers() -> None:
    repository = InMemoryTicketRepository()
    audit_log = AuditLog()
    service = TicketMutationService(repository, audit_log)
    ticket = _ticket()

    created = service.create_audited(ticket, "ticket_created", ticket.requester_user_id, {})
    saved = service.save(replace(created, state=TicketState.INFO_REQUIRED))

    assert repository.get(ticket.ticket_id) == saved
    assert audit_log.list_events()[0].event_type == "ticket_created"
    assert service.restore_if_current(saved, created)
    service.accept_committed(saved)
    assert repository.get(ticket.ticket_id) == saved


def test_compatibility_create_rolls_back_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = InMemoryTicketRepository()
    audit_log = AuditLog()
    service = TicketMutationService(repository, audit_log)
    ticket = _ticket()
    monkeypatch.setattr(
        audit_log, "record", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audit"))
    )

    with pytest.raises(RuntimeError, match="audit"):
        service.create_audited(ticket, "ticket_created", ticket.requester_user_id, {})

    assert repository.get(ticket.ticket_id) is None


def test_hosted_create_handles_collision_and_cache_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = InMemoryTicketRepository()
    audit_log = AuditLog()
    transaction = StubWorkflowTransaction()
    service = TicketMutationService(repository, audit_log, transaction)
    ticket = _ticket()
    monkeypatch.setattr(repository, "accept_committed", _raise_oserror)
    monkeypatch.setattr(audit_log, "refresh_from_store", _raise_oserror)

    assert service.create_audited(ticket, "ticket_created", ticket.requester_user_id, {})
    transaction.create_result = False
    with pytest.raises(AppError) as error:
        service.create_audited(ticket, "ticket_created", ticket.requester_user_id, {})
    assert error.value.code == "ticket_changed"


def test_compatibility_audited_update_rolls_back_on_atomic_audit_batch_failure() -> None:
    repository, expected, _second = _seed_pair()
    audit_log = AuditLog(event_store=RejectBatchAuditStore())
    service = TicketMutationService(repository, audit_log)
    proposed = replace(expected, state=TicketState.INFO_REQUIRED)
    with pytest.raises(RuntimeError, match="audit batch"):
        service.save_with_audits_if_current(
            expected,
            proposed,
            expected.requester_user_id,
            (("first", {}), ("second", {})),
        )
    assert repository.get(expected.ticket_id) == expected
    assert audit_log.list_events() == ()


def test_compatibility_audited_update_and_pair_commit_complete_groups() -> None:
    repository, first, second = _seed_pair()
    audit_log = AuditLog()
    service = TicketMutationService(repository, audit_log)

    updated = service.save_with_audits_if_current(
        first,
        replace(first, state=TicketState.INFO_REQUIRED),
        first.requester_user_id,
        (("first", {}), ("second", {})),
    )
    paired = service.save_pair_audited(
        (updated, second),
        (replace(updated, state=TicketState.CANCELLED), second),
        "tickets_linked",
        first.requester_user_id,
        {},
    )

    assert repository.get(first.ticket_id) == paired[0]
    assert [event.event_type for event in audit_log.list_events()] == [
        "first",
        "second",
        "tickets_linked",
    ]


def test_audited_update_rejects_an_empty_event_group() -> None:
    repository, expected, _second = _seed_pair()
    service = TicketMutationService(repository, AuditLog())

    with pytest.raises(ValueError, match="at least one audit event"):
        service.save_with_audits_if_current(
            expected, expected, expected.requester_user_id, ()
        )


def test_hosted_audited_update_handles_success_conflict_and_cache_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, expected, _second = _seed_pair()
    audit_log = AuditLog()
    transaction = StubWorkflowTransaction()
    service = TicketMutationService(repository, audit_log, transaction)
    proposed = replace(expected, state=TicketState.INFO_REQUIRED)
    monkeypatch.setattr(repository, "accept_committed", _raise_oserror)
    monkeypatch.setattr(audit_log, "refresh_from_store", _raise_oserror)

    committed = service.save_audited_if_current(
        expected, proposed, "ticket_changed", expected.requester_user_id, {}
    )
    assert committed == transaction.updated
    transaction.update_result = False
    with pytest.raises(AppError) as error:
        service.save_audited_if_current(
            expected, proposed, "ticket_changed", expected.requester_user_id, {}
        )
    assert error.value.code == "ticket_changed"


def test_compatibility_pair_rolls_back_first_when_second_conflicts() -> None:
    repository, first, second = _seed_pair()
    service = TicketMutationService(repository, AuditLog())
    repository.save(replace(second, state=TicketState.INFO_REQUIRED))

    with pytest.raises(AppError):
        service.save_pair_audited(
            (first, second),
            (replace(first, state=TicketState.CANCELLED), second),
            "tickets_linked",
            first.requester_user_id,
            {},
        )
    assert repository.get(first.ticket_id) == first


def test_compatibility_pair_rolls_back_both_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, first, second = _seed_pair()
    audit_log = AuditLog()
    service = TicketMutationService(repository, audit_log)
    monkeypatch.setattr(
        audit_log, "record", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audit"))
    )

    with pytest.raises(RuntimeError, match="audit"):
        service.save_pair_audited(
            (first, second),
            (replace(first, state=TicketState.CANCELLED), second),
            "tickets_linked",
            first.requester_user_id,
            {},
        )
    assert repository.get(first.ticket_id) == first
    assert repository.get(second.ticket_id) == second


def test_hosted_pair_handles_success_conflict_and_cache_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, first, second = _seed_pair()
    audit_log = AuditLog()
    transaction = StubWorkflowTransaction()
    service = TicketMutationService(repository, audit_log, transaction)
    monkeypatch.setattr(repository, "accept_committed", _raise_oserror)
    monkeypatch.setattr(audit_log, "refresh_from_store", _raise_oserror)
    proposed = (replace(first, state=TicketState.CANCELLED), second)

    committed = service.save_pair_audited(
        (first, second), proposed, "tickets_linked", first.requester_user_id, {}
    )
    assert transaction.paired == committed
    transaction.pair_result = False
    with pytest.raises(AppError) as error:
        service.save_pair_audited(
            (first, second), proposed, "tickets_linked", first.requester_user_id, {}
        )
    assert error.value.code == "ticket_changed"
