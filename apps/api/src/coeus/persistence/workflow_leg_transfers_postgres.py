"""Serializable two-manager cross-team workflow-leg transfer repository."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from coeus.application.ports.workflow_leg_transfers import WorkflowLegTransferStore
from coeus.domain.workflow_leg_transfers import (
    ProposeWorkflowLegTransfer,
    WorkflowLegTransferCommand,
    WorkflowLegTransferConflict,
    WorkflowLegTransferDenied,
    WorkflowLegTransferPreview,
    WorkflowLegTransferResult,
    WorkflowLegTransferState,
    command_hash,
    proposal_hash,
)
from coeus.persistence.organisation_authority_validation import transaction_time
from coeus.persistence.serializable_retry import retry_serializable_once
from coeus.persistence.workflow_leg_transfer_commands import (
    INSERT_PACKAGE,
    INSERT_TRANSFER,
    TRANSFER_FOR_UPDATE,
    UPDATE_TRANSFER,
    insert_command,
    lock_commands,
    lock_new_transfer,
    package_values,
    replay,
    transfer_values,
)
from coeus.persistence.workflow_leg_transfer_decisions import (
    apply_decision,
    authorise_decision,
    authorise_grants,
)
from coeus.persistence.workflow_leg_transfer_evidence import append_transfer_evidence
from coeus.persistence.workflow_leg_transfer_validation import (
    validate_grant,
    validate_proposal,
)
from coeus.persistence.workflow_transfer_work_updates import append_transfer_request_updates


class PostgresWorkflowLegTransferStore(WorkflowLegTransferStore):
    def __init__(self, engine: Engine, *, policy_buffer_minutes: int = 0) -> None:
        self._engine = engine
        self._policy_buffer_minutes = policy_buffer_minutes

    def preview(
        self, actor_user_id: UUID, proposal: ProposeWorkflowLegTransfer
    ) -> WorkflowLegTransferPreview:
        with self._engine.begin() as connection:
            now = transaction_time(connection)
            preview, _, _ = validate_proposal(connection, actor_user_id, proposal, now, lock=False)
            return preview

    def propose(
        self,
        actor_user_id: UUID,
        command_id: UUID,
        idempotency_key: str,
        proposal: ProposeWorkflowLegTransfer,
        expected_preview_hash: str,
    ) -> WorkflowLegTransferResult:
        return retry_serializable_once(
            lambda: self._propose_once(
                actor_user_id, command_id, idempotency_key, proposal, expected_preview_hash
            )
        )

    def decide(self, command: WorkflowLegTransferCommand) -> WorkflowLegTransferResult:
        return retry_serializable_once(lambda: self._decide_once(command))

    def _propose_once(
        self,
        actor: UUID,
        command_id: UUID,
        key: str,
        proposal: ProposeWorkflowLegTransfer,
        expected_preview: str,
    ) -> WorkflowLegTransferResult:
        connection = self._engine.connect().execution_options(isolation_level="SERIALIZABLE")
        try:
            with connection.begin():
                lock_commands(connection, command_id, actor, key)
                now = transaction_time(connection)
                replayed = replay(
                    connection, command_id, actor, key, proposal_hash(actor, proposal)
                )
                if replayed is not None:
                    validate_grant(
                        connection,
                        actor,
                        proposal.authorising_grant_id,
                        proposal.expected_grant_version,
                        proposal.source_unit_id,
                        now,
                    )
                    return replayed
                lock_new_transfer(connection, proposal.transfer_id)
                preview, _, _ = validate_proposal(connection, actor, proposal, now, lock=True)
                if preview.preview_hash != expected_preview:
                    raise WorkflowLegTransferConflict("transfer preview is no longer current")
                connection.execute(
                    text(INSERT_TRANSFER),
                    transfer_values(actor, proposal, preview.preview_hash, now),
                )
                for package in proposal.packages:
                    connection.execute(
                        text(INSERT_PACKAGE), package_values(proposal.transfer_id, package)
                    )
                insert_command(
                    connection,
                    command_id,
                    actor,
                    key,
                    proposal.transfer_id,
                    "propose",
                    proposal_hash(actor, proposal),
                    WorkflowLegTransferState.PROPOSED,
                    1,
                    now,
                )
                append_transfer_evidence(
                    connection,
                    proposal.transfer_id,
                    proposal.ticket_id,
                    actor,
                    WorkflowLegTransferState.PROPOSED,
                    1,
                    now,
                )
                append_transfer_request_updates(connection, proposal, actor, now)
                return WorkflowLegTransferResult(
                    proposal.transfer_id, WorkflowLegTransferState.PROPOSED, 1, False
                )
        finally:
            connection.close()

    def _decide_once(self, command: WorkflowLegTransferCommand) -> WorkflowLegTransferResult:
        connection = self._engine.connect().execution_options(isolation_level="SERIALIZABLE")
        try:
            with connection.begin():
                lock_commands(
                    connection, command.command_id, command.actor_user_id, command.idempotency_key
                )
                replayed = replay(
                    connection,
                    command.command_id,
                    command.actor_user_id,
                    command.idempotency_key,
                    command_hash(command),
                )
                if replayed is not None:
                    transfer = (
                        connection.execute(
                            text("SELECT * FROM workflow_leg_transfers WHERE transfer_id=:id"),
                            {"id": replayed.transfer_id},
                        )
                        .mappings()
                        .first()
                    )
                    if transfer is None:
                        raise WorkflowLegTransferDenied("workflow-leg transfer is unavailable")
                    authorise_grants(connection, command, transfer, transaction_time(connection))
                    return replayed
                transfer = (
                    connection.execute(
                        text(TRANSFER_FOR_UPDATE), {"transfer_id": command.transfer_id}
                    )
                    .mappings()
                    .first()
                )
                if transfer is None:
                    raise WorkflowLegTransferDenied("workflow-leg transfer is unavailable")
                now = transaction_time(connection)
                authorise_decision(connection, command, transfer, now)
                if (
                    transfer["state"] != "proposed"
                    or int(transfer["version"]) != command.expected_transfer_version
                ):
                    raise WorkflowLegTransferConflict("workflow-leg transfer evidence changed")
                state, ticket_version, ownership_version = apply_decision(
                    connection, command, transfer, now, self._policy_buffer_minutes
                )
                version = int(transfer["version"]) + 1
                connection.execute(
                    text(UPDATE_TRANSFER),
                    {
                        "transfer_id": command.transfer_id,
                        "state": state.value,
                        "target_manager": command.actor_user_id
                        if command.action in {"accept", "reject"}
                        else None,
                        "ticket_version": ticket_version,
                        "ownership_version": ownership_version,
                        "reason": command.reason,
                        "version": version,
                        "at": now,
                    },
                )
                insert_command(
                    connection,
                    command.command_id,
                    command.actor_user_id,
                    command.idempotency_key,
                    command.transfer_id,
                    command.action,
                    command_hash(command),
                    state,
                    version,
                    now,
                )
                append_transfer_evidence(
                    connection,
                    command.transfer_id,
                    transfer["ticket_id"],
                    command.actor_user_id,
                    state,
                    version,
                    now,
                )
                return WorkflowLegTransferResult(command.transfer_id, state, version, False)
        finally:
            connection.close()
