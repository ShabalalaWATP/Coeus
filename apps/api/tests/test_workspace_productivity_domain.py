"""Invariants that keep saved workspace records safe to store and replay."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from coeus.domain.team_task_board import TeamBoardColumn, TeamBoardScope
from coeus.domain.workspace_productivity import (
    PackageTemplate,
    ProductivityCommand,
    SavedBoardFilters,
    SavedBoardView,
    WorkspaceStoreLink,
)

NOW = datetime(2026, 8, 4, 12, tzinfo=UTC)


def test_board_filters_accept_a_bounded_distinct_selection() -> None:
    filters = SavedBoardFilters(
        scope=TeamBoardScope.DESCENDANTS,
        include_completed=True,
        columns=(TeamBoardColumn.READY, TeamBoardColumn.BLOCKED),
        unit_ids=(uuid4(), uuid4()),
        priority="High",
        due_from=date(2026, 8, 1),
        due_to=date(2026, 8, 31),
    )

    assert filters.scope is TeamBoardScope.DESCENDANTS
    assert len(filters.columns) == 2


def test_board_filters_reject_repeated_statuses_or_teams() -> None:
    with pytest.raises(ValueError, match="saved board statuses are invalid"):
        SavedBoardFilters(columns=(TeamBoardColumn.READY, TeamBoardColumn.READY))
    unit_id = uuid4()
    with pytest.raises(ValueError, match="saved board team filters are invalid"):
        SavedBoardFilters(unit_ids=(unit_id, unit_id))
    with pytest.raises(ValueError, match="saved board team filters are invalid"):
        SavedBoardFilters(unit_ids=tuple(uuid4() for _ in range(21)))


def test_board_filters_reject_an_inverted_date_window_and_untrimmed_priority() -> None:
    with pytest.raises(ValueError, match="due_from cannot be after due_to"):
        SavedBoardFilters(due_from=date(2026, 8, 31), due_to=date(2026, 8, 1))
    with pytest.raises(ValueError, match="priority must contain"):
        SavedBoardFilters(priority=" High ")


def test_a_single_open_bound_is_allowed() -> None:
    assert SavedBoardFilters(due_from=date(2026, 8, 31)).due_to is None
    assert SavedBoardFilters(due_to=date(2026, 8, 1)).due_from is None


def _view(name: str = "Urgent work", version: int = 1) -> SavedBoardView:
    return SavedBoardView(uuid4(), uuid4(), uuid4(), name, SavedBoardFilters(), version, NOW)


def test_a_saved_view_needs_a_trimmed_name_and_a_positive_version() -> None:
    assert _view().version == 1
    with pytest.raises(ValueError, match="saved view name must contain"):
        _view(name=" Urgent ")
    with pytest.raises(ValueError, match="saved view name must contain"):
        _view(name="")
    with pytest.raises(ValueError, match="saved view name must contain"):
        _view(name="x" * 81)
    with pytest.raises(ValueError, match="saved view version must be positive"):
        _view(version=0)


def test_a_saved_name_cannot_smuggle_control_characters() -> None:
    with pytest.raises(ValueError, match="cannot contain control characters"):
        _view(name="Urgent\x07work")


def _template(**overrides: object) -> PackageTemplate:
    values: dict[str, object] = {
        "template_id": uuid4(),
        "unit_id": uuid4(),
        "owner_user_id": uuid4(),
        "name": "Assessment",
        "package_titles": ("Research", "Draft"),
        "estimated_minutes": 120,
        "priority": 2,
        "version": 1,
        "updated_at": NOW,
    }
    values.update(overrides)
    return PackageTemplate(**values)  # type: ignore[arg-type]


def test_a_template_bounds_its_titles_effort_and_priority() -> None:
    assert _template().estimated_minutes == 120
    assert _template(estimated_minutes=None, priority=None).priority is None
    with pytest.raises(ValueError, match="between one and 20 package titles"):
        _template(package_titles=())
    with pytest.raises(ValueError, match="between one and 20 package titles"):
        _template(package_titles=tuple(f"Step {index}" for index in range(21)))
    with pytest.raises(ValueError, match="package title must contain"):
        _template(package_titles=("Research", " Draft "))
    with pytest.raises(ValueError, match="estimated minutes must be between"):
        _template(estimated_minutes=14)
    with pytest.raises(ValueError, match="estimated minutes must be between"):
        _template(estimated_minutes=10_081)
    with pytest.raises(ValueError, match="priority must be between one and five"):
        _template(priority=6)


def _link(**overrides: object) -> WorkspaceStoreLink:
    values: dict[str, object] = {
        "link_id": uuid4(),
        "owner_user_id": uuid4(),
        "unit_id": uuid4(),
        "source_type": "ticket",
        "source_id": uuid4(),
        "target_type": "product",
        "target_id": uuid4(),
        "label": "Regional assessment",
        "version": 1,
        "updated_at": NOW,
    }
    values.update(overrides)
    return WorkspaceStoreLink(**values)  # type: ignore[arg-type]


def test_a_store_link_only_joins_known_record_kinds() -> None:
    assert _link(source_type="work_package", target_type="project").target_type == "project"
    with pytest.raises(ValueError, match="Store link source is invalid"):
        _link(source_type="person")
    with pytest.raises(ValueError, match="Store link target is invalid"):
        _link(target_type="report")
    with pytest.raises(ValueError, match="Store link label must contain"):
        _link(label="")
    with pytest.raises(ValueError, match="Store link version must be positive"):
        _link(version=0)


def test_a_command_hash_covers_the_operation_and_its_payload() -> None:
    payload = {"unit_id": uuid4(), "name": "Urgent"}
    command = ProductivityCommand(uuid4(), "key-1", uuid4(), "save_view", payload)
    same = ProductivityCommand(uuid4(), "key-2", uuid4(), "save_view", dict(payload))
    other_operation = ProductivityCommand(uuid4(), "key-1", uuid4(), "delete_view", payload)
    other_payload = ProductivityCommand(
        uuid4(), "key-1", uuid4(), "save_view", {**payload, "name": "Routine"}
    )

    assert command.request_hash == same.request_hash
    assert command.request_hash != other_operation.request_hash
    assert command.request_hash != other_payload.request_hash


def test_a_command_needs_a_trimmed_key_and_operation() -> None:
    with pytest.raises(ValueError, match="idempotency key must contain"):
        ProductivityCommand(uuid4(), " key ", uuid4(), "save_view", {})
    with pytest.raises(ValueError, match="operation must contain"):
        ProductivityCommand(uuid4(), "key-1", uuid4(), "", {})
