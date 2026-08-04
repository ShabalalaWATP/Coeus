"""Transactional port for disabled organisation grant commands."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from coeus.domain.organisation import OrganisationManagementGrant
from coeus.domain.organisation_authority import (
    GrantCommandResult,
    RevokeManagementGrantCommand,
)


class OrganisationGrantCommandStore(Protocol):
    def replay_result(
        self,
        *,
        command_id: UUID,
        idempotency_key: str,
        request_hash: str,
        command_type: str,
        actor_user_id: UUID,
        grant_id: UUID,
    ) -> GrantCommandResult | None: ...

    def create_grant(
        self,
        grant: OrganisationManagementGrant,
        *,
        command_id: UUID,
        idempotency_key: str,
        request_hash: str,
        actor_user_id: UUID,
        management_grant_id: UUID,
        source_expected_version: int,
        occurred_at: datetime,
    ) -> GrantCommandResult: ...

    def revoke_grant(
        self,
        command: RevokeManagementGrantCommand,
        *,
        request_hash: str,
        management_grant_id: UUID,
        occurred_at: datetime,
    ) -> GrantCommandResult: ...
