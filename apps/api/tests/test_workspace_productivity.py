from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.team_task_board import TeamBoardColumn, TeamBoardScope
from coeus.domain.workspace_productivity import (
    PackageTemplate,
    ProductivityCommand,
    RecordPage,
    SavedBoardFilters,
    SavedBoardView,
    WorkspaceStoreLink,
)
from coeus.services.workspace_productivity import WorkspaceProductivityService


def test_saved_board_filters_are_bounded_and_date_ordered() -> None:
    filters = SavedBoardFilters(
        TeamBoardScope.DESCENDANTS,
        True,
        (TeamBoardColumn.BLOCKED,),
        (uuid4(),),
        "High",
        date(2026, 8, 1),
        date(2026, 8, 31),
    )
    view = SavedBoardView(uuid4(), uuid4(), uuid4(), "Blocked work", filters, 1, datetime.now(UTC))
    assert view.filters.columns == (TeamBoardColumn.BLOCKED,)
    with pytest.raises(ValueError, match="due_from"):
        SavedBoardFilters(due_from=date(2026, 9, 1), due_to=date(2026, 8, 1))
    with pytest.raises(ValueError, match="team filters"):
        unit_id = uuid4()
        SavedBoardFilters(unit_ids=(unit_id, unit_id))


def test_templates_and_idempotency_payloads_reject_unbounded_values() -> None:
    with pytest.raises(ValueError, match="between one and 20"):
        PackageTemplate(uuid4(), uuid4(), uuid4(), "Empty", (), None, None, 1, datetime.now(UTC))
    with pytest.raises(ValueError, match="trimmed"):
        ProductivityCommand(uuid4(), " key ", uuid4(), "save_view", {})
    first = ProductivityCommand(uuid4(), "key", uuid4(), "save_view", {"name": "One"})
    second = ProductivityCommand(uuid4(), "key", first.actor_user_id, "save_view", {"name": "One"})
    assert first.request_hash == second.request_hash


def test_store_links_are_hidden_immediately_when_product_access_is_revoked() -> None:
    actor = UserAccount(uuid4(), "analyst", "Analyst", frozenset(), frozenset(), "hash", True, 1)
    link = WorkspaceStoreLink(
        uuid4(),
        actor.user_id,
        uuid4(),
        "ticket",
        uuid4(),
        "product",
        uuid4(),
        "Stored title",
        1,
        datetime.now(UTC),
    )
    relational = _LinkStore(link)
    details = _ProductResolver("Current title")
    service = WorkspaceProductivityService(relational, details, None)  # type: ignore[arg-type]

    visible = service.list_store_links(
        actor, link.unit_id, link.source_type, link.source_id, None, 50
    )
    assert visible.items[0].label == "Current title"

    details.allowed = False
    hidden = service.list_store_links(
        actor, link.unit_id, link.source_type, link.source_id, None, 50
    )
    assert hidden.items == ()
    assert hidden.next_cursor is None


class _LinkStore:
    def __init__(self, link: WorkspaceStoreLink) -> None:
        self.link = link

    def list_store_links(self, *_args):
        return RecordPage((self.link,), None)


class _ProductResolver:
    def __init__(self, title: str) -> None:
        self.title = title
        self.allowed = True

    def get_visible_product(self, _actor, _target_id):
        if not self.allowed:
            raise AppError(404, "product_not_found", "Product was not found.")
        return SimpleNamespace(metadata=SimpleNamespace(title=self.title))
