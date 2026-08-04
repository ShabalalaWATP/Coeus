from datetime import UTC, datetime
from uuid import uuid4

from coeus.domain.team_task_board import TeamTaskBoard
from coeus.services.team_task_board import TeamTaskBoardService


class _Store:
    def __init__(self, board: TeamTaskBoard) -> None:
        self.board = board
        self.arguments = None

    def get_board(self, actor_id, unit_id, **options):  # type: ignore[no-untyped-def]
        self.arguments = (actor_id, unit_id, options)
        return self.board


def test_service_forwards_actor_scope_and_bounds() -> None:
    actor_id, unit_id = uuid4(), uuid4()
    board = TeamTaskBoard(unit_id, (), datetime(2026, 8, 3, tzinfo=UTC), False)
    store = _Store(board)

    assert (
        TeamTaskBoardService(store).get_board(actor_id, unit_id, include_completed=True, limit=25)
        is board
    )
    assert store.arguments == (
        actor_id,
        unit_id,
        {"include_completed": True, "limit": 25},
    )
