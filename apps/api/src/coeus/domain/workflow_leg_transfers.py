"""Two-manager transfer of work between delivery teams, never personnel."""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from coeus.domain.organisation_validation import aware, optional_text, text_value
from coeus.domain.team_task_ownership import WorkflowLeg


class PackageTransferDisposition(StrEnum):
    TRANSFER = "transfer"
    COMPLETE = "complete"
    CANCEL = "cancel"
    RETAIN = "retain"


class WorkflowLegTransferState(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class WorkflowLegTransferDenied(PermissionError):
    pass


class WorkflowLegTransferConflict(ValueError):
    pass


@dataclass(frozen=True)
class PackageTransferPlan:
    package_id: UUID
    disposition: PackageTransferDisposition
    expected_version: int
    reservation_id: UUID | None = None
    reservation_idempotency_key: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    reserved_minutes: int | None = None

    def __post_init__(self) -> None:
        if self.expected_version < 1:
            raise ValueError("package version must be positive")
        reservation_values = (
            self.reservation_id,
            self.reservation_idempotency_key,
            self.starts_at,
            self.ends_at,
            self.reserved_minutes,
        )
        required = self.disposition is PackageTransferDisposition.TRANSFER
        if any(value is not None for value in reservation_values) != required or (
            required and any(value is None for value in reservation_values)
        ):
            raise ValueError("transferred packages require a complete reservation plan")
        aware(self.starts_at, "starts_at")
        aware(self.ends_at, "ends_at")
        if required:
            assert self.starts_at is not None and self.ends_at is not None
            assert self.reserved_minutes is not None
            assert self.reservation_idempotency_key is not None
            if (
                self.starts_at >= self.ends_at
                or self.reserved_minutes < 15
                or self.reserved_minutes % 15
            ):
                raise ValueError("reservation plan is invalid")
            text_value(self.reservation_idempotency_key, "reservation_idempotency_key", 128)


@dataclass(frozen=True)
class ProposeWorkflowLegTransfer:
    transfer_id: UUID
    ticket_id: UUID
    workflow_leg: WorkflowLeg
    source_unit_id: UUID
    target_unit_id: UUID
    target_user_id: UUID
    expected_ownership_version: int
    expected_ticket_version: int
    expected_ticket_source_hash: str
    authorising_grant_id: UUID
    expected_grant_version: int
    expires_at: datetime
    packages: tuple[PackageTransferPlan, ...]
    reason: str

    def __post_init__(self) -> None:
        if self.source_unit_id == self.target_unit_id:
            raise ValueError("cross-team transfer requires distinct teams")
        if min(self.expected_ownership_version, self.expected_ticket_version) < 1:
            raise ValueError("transfer evidence versions must be positive")
        if len(self.expected_ticket_source_hash) != 64:
            raise ValueError("ticket source hash is invalid")
        aware(self.expires_at, "expires_at")
        text_value(self.reason, "reason", 500)
        if not self.packages or len(self.packages) > 64:
            raise ValueError("transfer requires between one and 64 package dispositions")
        if len({item.package_id for item in self.packages}) != len(self.packages):
            raise ValueError("package dispositions must be unique")
        if not any(
            item.disposition is PackageTransferDisposition.TRANSFER for item in self.packages
        ):
            raise ValueError("at least one package must transfer")


@dataclass(frozen=True)
class WorkflowLegTransferPreview:
    preview_hash: str
    transfer_id: UUID
    ticket_id: UUID
    source_unit_id: UUID
    target_unit_id: UUID
    package_count: int
    transfer_count: int
    expires_at: datetime


@dataclass(frozen=True)
class WorkflowLegTransferCommand:
    command_id: UUID
    idempotency_key: str
    actor_user_id: UUID
    transfer_id: UUID
    expected_transfer_version: int
    action: str
    preview_hash: str | None = None
    grant_id: UUID | None = None
    expected_grant_version: int | None = None
    target_membership_id: UUID | None = None
    expected_target_membership_version: int | None = None
    expected_target_account_credential_version: int | None = None
    expected_target_account_source_hash: str | None = None
    assignment_grant_id: UUID | None = None
    expected_assignment_grant_version: int | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        text_value(self.idempotency_key, "idempotency_key", 128)
        optional_text(self.reason, "reason", 500)
        if self.expected_transfer_version < 1 or self.action not in {
            "accept",
            "reject",
            "cancel",
            "expire",
        }:
            raise ValueError("transfer command is invalid")


@dataclass(frozen=True)
class WorkflowLegTransferResult:
    transfer_id: UUID
    state: WorkflowLegTransferState
    version: int
    replayed: bool


def proposal_hash(actor_user_id: UUID, proposal: ProposeWorkflowLegTransfer) -> str:
    payload = {"actor_user_id": str(actor_user_id), **_proposal_payload(proposal)}
    return _hash(payload)


def preview_hash(
    actor_user_id: UUID, proposal: ProposeWorkflowLegTransfer, inventory: object
) -> str:
    return _hash({"proposal_hash": proposal_hash(actor_user_id, proposal), "inventory": inventory})


def command_hash(command: WorkflowLegTransferCommand) -> str:
    return _hash(
        {
            key: str(value)
            for key, value in vars(command).items()
            if key not in {"command_id", "idempotency_key"}
        }
    )


def _proposal_payload(proposal: ProposeWorkflowLegTransfer) -> dict[str, object]:
    data = vars(proposal).copy()
    data["workflow_leg"] = proposal.workflow_leg.value
    data["packages"] = [
        {key: str(value) for key, value in vars(item).items()} for item in proposal.packages
    ]
    return {
        key: str(value) if isinstance(value, (UUID, datetime)) else value
        for key, value in data.items()
    }


def _hash(payload: object) -> str:
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
