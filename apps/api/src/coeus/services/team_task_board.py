"""Read service for authorised direct-team task boards."""

from uuid import UUID

from coeus.application.ports.team_task_board import TeamTaskBoardStore
from coeus.domain.team_task_board import TeamBoardQuery, TeamTaskBoard


class TeamTaskBoardService:
    def __init__(self, store: TeamTaskBoardStore) -> None:
        self._store = store

    def get_board(
        self,
        actor_user_id: UUID,
        unit_id: UUID,
        query: TeamBoardQuery | None = None,
        *,
        include_completed: bool = False,
        limit: int = 50,
    ) -> TeamTaskBoard:
        if query is None:
            return self._store.get_board(
                actor_user_id,
                unit_id,
                include_completed=include_completed,
                limit=limit,
            )
        return self._store.get_board(actor_user_id, unit_id, query=query)
