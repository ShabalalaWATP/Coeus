"""Narrow access-data ports used by application services."""

from typing import Protocol
from uuid import UUID

from coeus.domain.auth import UserAccount


class UserLookup(Protocol):
    def get_user(self, user_id: UUID) -> UserAccount | None: ...


class ActiveAcgReader(Protocol):
    def active_acg_ids_for_user(self, user_id: UUID) -> frozenset[UUID]: ...
