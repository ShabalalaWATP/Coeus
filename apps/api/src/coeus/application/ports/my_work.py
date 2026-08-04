"""Application boundary for canonical actor-only work."""

from typing import Protocol
from uuid import UUID

from coeus.domain.my_work import MyWorkColumn, MyWorkPage


class MyWorkStore(Protocol):
    def list_my_work(
        self,
        actor_user_id: UUID,
        *,
        include_completed: bool,
        column: MyWorkColumn | None,
        cursor: str | None,
        limit: int,
    ) -> MyWorkPage: ...
