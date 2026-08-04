"""Persistence row decoding and idempotency checks for personnel transfers."""

from hashlib import sha256
from uuid import UUID

from sqlalchemy.engine import RowMapping

from coeus.domain.organisation import MembershipRole
from coeus.domain.organisation_transfer import (
    PersonnelTransferCommand,
    PersonnelTransferIdempotencyConflict,
    PersonnelTransferRequest,
    PersonnelTransferResult,
    PersonnelTransferStatus,
)


def decode_command(row: RowMapping) -> PersonnelTransferCommand:
    request = PersonnelTransferRequest(
        UUID(str(row["source_membership_id"])),
        UUID(str(row["target_membership_id"])),
        UUID(str(row["user_id"])),
        UUID(str(row["source_unit_id"])),
        UUID(str(row["target_unit_id"])),
        int(str(row["expected_membership_version"])),
        int(str(row["expected_target_unit_version"])),
        MembershipRole(str(row["target_role"])),
        bool(row["assignment_eligible"]),
        row["effective_at"],
        UUID(str(row["source_authorising_grant_id"])),
        UUID(str(row["target_authorising_grant_id"])),
        str(row["reason"]),
    )
    return PersonnelTransferCommand(
        UUID(str(row["command_id"])),
        str(row["idempotency_key"]),
        UUID(str(row["actor_user_id"])),
        request,
        str(row["request_hash"]),
    )


def replay(
    rows: tuple[RowMapping, ...], command: PersonnelTransferCommand
) -> PersonnelTransferResult | None:
    if not rows:
        return None
    if len(rows) != 1:
        raise PersonnelTransferIdempotencyConflict(
            "command and idempotency key identify different personnel transfers"
        )
    row = rows[0]
    request = command.request
    stored = decode_command(row)
    matches = (
        stored == command and str(row["reason_hash"]) == sha256(request.reason.encode()).hexdigest()
    )
    if not matches:
        raise PersonnelTransferIdempotencyConflict(
            "command or idempotency key is already used by another personnel transfer"
        )
    return PersonnelTransferResult(
        command.command_id,
        request.source_membership_id,
        request.target_membership_id,
        PersonnelTransferStatus(str(row["status"])),
        int(str(row["source_result_version"])),
        int(str(row["target_result_version"])),
        True,
        str(row["failure_code"]),
    )
