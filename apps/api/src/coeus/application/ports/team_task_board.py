"""Persistence contract for direct-team task boards."""

from typing import Protocol
from uuid import UUID

from coeus.domain.team_task_board import TeamBoardQuery, TeamTaskBoard


class TeamTaskBoardStore(Protocol):
    def get_board(
        self,
        actor_user_id: UUID,
        unit_id: UUID,
        query: TeamBoardQuery | None = None,
        *,
        include_completed: bool = False,
        limit: int = 50,
    ) -> TeamTaskBoard: ...
