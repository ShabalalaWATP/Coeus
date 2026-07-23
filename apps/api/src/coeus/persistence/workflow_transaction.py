"""PostgreSQL transaction owner for QC release state and side-effect intent."""

from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from coeus.domain.store import StoreProduct
from coeus.domain.submission_authority import SubmissionCommitResult
from coeus.domain.tickets import TicketRecord
from coeus.domain.workflow_authority import WorkflowCommitAuthority, WorkflowCommitResult
from coeus.domain.workflow_transaction import (
    ReleaseNotificationIntent,
    WorkflowAuditIntent,
    WorkflowOutboxIntent,
)
from coeus.persistence.audit_store import AUDIT_TABLE_SQL
from coeus.persistence.codec import encode_value
from coeus.persistence.database_url import synchronous_database_url
from coeus.persistence.relational_schema import ensure_relational_schema
from coeus.persistence.state_store import (
    _encoded_ticket_hash,
    _encoded_ticket_id,
    _shadow_ticket_payload,
)
from coeus.persistence.store_projection_write import existing_embedding_hashes, save_product
from coeus.persistence.submission_authority import lock_submission_authority
from coeus.persistence.ticket_shadow_schema import ensure_ticket_shadow_schema
from coeus.persistence.workflow_authority import lock_workflow_authority
from coeus.persistence.workflow_transaction_writes import WorkflowTransactionWrites


class PostgresWorkflowTransaction(WorkflowTransactionWrites):
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(synchronous_database_url(database_url), pool_pre_ping=True)

    def commit_ticket_create(
        self,
        ticket: TicketRecord,
        audit: WorkflowAuditIntent,
    ) -> bool:
        return self._commit_ticket_create(ticket, audit, None) is WorkflowCommitResult.COMMITTED

    def commit_authorised_ticket_create(
        self,
        ticket: TicketRecord,
        audit: WorkflowAuditIntent,
        authority: WorkflowCommitAuthority,
    ) -> WorkflowCommitResult:
        return self._commit_ticket_create(ticket, audit, authority)

    def _commit_ticket_create(
        self,
        ticket: TicketRecord,
        audit: WorkflowAuditIntent,
        authority: WorkflowCommitAuthority | None,
    ) -> WorkflowCommitResult:
        payload = encode_value(ticket)
        ticket_id = _encoded_ticket_id(payload)
        with self._engine.begin() as connection:
            self._prepare(connection)
            if authority is not None:
                authority_result = lock_workflow_authority(connection, authority)
                if authority_result is not WorkflowCommitResult.COMMITTED:
                    return authority_result
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:ticket_id, 0))"),
                {"ticket_id": ticket_id},
            )
            exists = connection.execute(
                text(
                    "SELECT 1 FROM coeus_ticket_aggregates "
                    "WHERE ticket_id = CAST(:ticket_id AS uuid)"
                ),
                {"ticket_id": ticket_id},
            ).scalar_one_or_none()
            if exists is not None:
                return WorkflowCommitResult.TICKET_CHANGED
            self._write_ticket(connection, payload, ticket_id)
            self._append_audit(connection, audit)
        return WorkflowCommitResult.COMMITTED

    def commit_ticket_update(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        audits: tuple[WorkflowAuditIntent, ...],
        outbox: tuple[WorkflowOutboxIntent, ...] = (),
    ) -> bool:
        return (
            self._commit_ticket_update(expected, updated, audits, outbox, None)
            is WorkflowCommitResult.COMMITTED
        )

    def commit_authorised_ticket_update(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        audits: tuple[WorkflowAuditIntent, ...],
        authority: WorkflowCommitAuthority,
        outbox: tuple[WorkflowOutboxIntent, ...] = (),
    ) -> WorkflowCommitResult:
        return self._commit_ticket_update(expected, updated, audits, outbox, authority)

    def _commit_ticket_update(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        audits: tuple[WorkflowAuditIntent, ...],
        outbox: tuple[WorkflowOutboxIntent, ...],
        authority: WorkflowCommitAuthority | None,
    ) -> WorkflowCommitResult:
        expected_payload = encode_value(expected)
        updated_payload = encode_value(updated)
        with self._engine.begin() as connection:
            self._prepare(connection)
            if authority is not None:
                authority_result = lock_workflow_authority(connection, authority)
                if authority_result is not WorkflowCommitResult.COMMITTED:
                    return authority_result
            ticket_id = self._lock_current(connection, expected_payload)
            if ticket_id is None:
                return WorkflowCommitResult.TICKET_CHANGED
            version = self._write_ticket(connection, updated_payload, ticket_id)
            self._append_audits(connection, audits)
            self._append_outbox_intents(connection, updated.ticket_id, version, outbox)
        return WorkflowCommitResult.COMMITTED

    def commit_product_submission(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        audits: tuple[WorkflowAuditIntent, ...],
        actor_user_id: UUID,
        required_acg_ids: frozenset[UUID],
    ) -> SubmissionCommitResult:
        """Fence live account and ACG authority with the ticket commit."""
        expected_payload = encode_value(expected)
        updated_payload = encode_value(updated)
        with self._engine.begin() as connection:
            self._prepare(connection)
            authority = lock_submission_authority(connection, actor_user_id, required_acg_ids)
            if authority is not SubmissionCommitResult.COMMITTED:
                return authority
            ticket_id = self._lock_current(connection, expected_payload)
            if ticket_id is None:
                return SubmissionCommitResult.TICKET_CHANGED
            self._write_ticket(connection, updated_payload, ticket_id)
            self._append_audits(connection, audits)
        return SubmissionCommitResult.COMMITTED

    def commit_ticket_pair(
        self,
        expected: tuple[TicketRecord, TicketRecord],
        updated: tuple[TicketRecord, TicketRecord],
        audits: tuple[WorkflowAuditIntent, ...],
    ) -> bool:
        expected_payloads = tuple(encode_value(ticket) for ticket in expected)
        expected_ids = {_encoded_ticket_id(payload) for payload in expected_payloads}
        updated_by_id = {
            _encoded_ticket_id(payload): payload for payload in map(encode_value, updated)
        }
        if len(expected_ids) != 2 or len(updated_by_id) != 2 or set(updated_by_id) != expected_ids:
            raise ValueError("Updated ticket identities must match expected identities.")
        ordered = tuple(sorted(expected_payloads, key=_encoded_ticket_id))
        with self._engine.begin() as connection:
            self._prepare(connection)
            ticket_ids = tuple(self._lock_current(connection, payload) for payload in ordered)
            locked_ids = tuple(ticket_id for ticket_id in ticket_ids if ticket_id is not None)
            if len(locked_ids) != 2:
                return False
            for ticket_id in locked_ids:
                self._write_ticket(connection, updated_by_id[ticket_id], ticket_id)
            self._append_audits(connection, audits)
        return True

    def commit_qc_release(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        product: StoreProduct,
        audit: WorkflowAuditIntent,
        notification: ReleaseNotificationIntent | None,
    ) -> bool:
        return (
            self._commit_qc_release(expected, updated, product, audit, notification, None)
            is WorkflowCommitResult.COMMITTED
        )

    def commit_authorised_qc_release(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        product: StoreProduct,
        audit: WorkflowAuditIntent,
        notification: ReleaseNotificationIntent | None,
        authority: WorkflowCommitAuthority,
    ) -> WorkflowCommitResult:
        return self._commit_qc_release(expected, updated, product, audit, notification, authority)

    def _commit_qc_release(
        self,
        expected: TicketRecord,
        updated: TicketRecord,
        product: StoreProduct,
        audit: WorkflowAuditIntent,
        notification: ReleaseNotificationIntent | None,
        authority: WorkflowCommitAuthority | None,
    ) -> WorkflowCommitResult:
        expected_payload = encode_value(expected)
        updated_payload = encode_value(updated)
        with self._engine.begin() as connection:
            self._prepare(connection)
            if authority is not None:
                authority_result = lock_workflow_authority(connection, authority)
                if authority_result is not WorkflowCommitResult.COMMITTED:
                    return authority_result
            ticket_id = self._lock_current(connection, expected_payload)
            if ticket_id is None:
                return WorkflowCommitResult.TICKET_CHANGED
            hashes = existing_embedding_hashes(connection, (product.product_id,))
            save_product(connection, product, None, hashes)
            version = self._write_ticket(connection, updated_payload, ticket_id)
            self._append_audit(connection, audit)
            if notification is not None:
                self._append_notification(connection, expected.ticket_id, version, notification)
        return WorkflowCommitResult.COMMITTED

    @staticmethod
    def _prepare(connection: Connection) -> None:
        ensure_relational_schema(connection)
        ensure_ticket_shadow_schema(connection)
        connection.execute(text(AUDIT_TABLE_SQL))

    @staticmethod
    def _lock_current(connection: Connection, expected_payload: dict[str, object]) -> str | None:
        ticket_id = _encoded_ticket_id(expected_payload)
        current_hash = connection.execute(
            text(
                "SELECT canonical_hash FROM coeus_ticket_aggregates "
                "WHERE ticket_id = CAST(:ticket_id AS uuid) FOR UPDATE"
            ),
            {"ticket_id": ticket_id},
        ).scalar_one_or_none()
        return ticket_id if current_hash == _encoded_ticket_hash(expected_payload) else None

    @staticmethod
    def _write_ticket(
        connection: Connection, updated_payload: dict[str, object], ticket_id: str
    ) -> int:
        _shadow_ticket_payload(connection, {"tickets": [updated_payload]}, reconcile=False)
        return int(
            connection.execute(
                text(
                    "SELECT version FROM coeus_ticket_aggregates "
                    "WHERE ticket_id = CAST(:ticket_id AS uuid)"
                ),
                {"ticket_id": ticket_id},
            ).scalar_one()
        )
