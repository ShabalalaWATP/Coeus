"""Actor-only canonical personal work service."""

from uuid import UUID

from coeus.application.ports.my_work import MyWorkStore
from coeus.domain.my_work import MyWorkColumn, MyWorkPage


class MyWorkService:
    def __init__(self, store: MyWorkStore) -> None:
        self._store = store

    def list_my_work(
        self,
        actor_user_id: UUID,
        *,
        include_completed: bool = False,
        column: MyWorkColumn | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> MyWorkPage:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between one and 100")
        return self._store.list_my_work(
            actor_user_id,
            include_completed=include_completed,
            column=column,
            cursor=cursor,
            limit=limit,
        )
