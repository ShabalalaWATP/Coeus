"""PostgreSQL locking and decoding for submission authority snapshots."""

from uuid import UUID

from sqlalchemy.engine import Connection

from coeus.domain.submission_authority import (
    SubmissionCommitResult,
    submission_authority_result,
)
from coeus.persistence.authority_locks import lock_authority_namespaces
from coeus.persistence.codec import decode_value


def lock_submission_authority(
    connection: Connection,
    actor_user_id: UUID,
    required_acg_ids: frozenset[UUID],
) -> SubmissionCommitResult:
    payloads = lock_authority_namespaces(connection, ("users", "access"))
    users = tuple(decode_value(item) for item in payloads.get("users", {}).get("users", []))
    access = payloads.get("access", {})
    acgs = tuple(decode_value(item) for item in access.get("acgs", []))
    memberships = tuple(decode_value(item) for item in access.get("memberships", []))
    return submission_authority_result(users, acgs, memberships, actor_user_id, required_acg_ids)
