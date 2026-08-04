"""Store links stay bound to what the reader can currently open."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from coeus.core.errors import AppError
from coeus.domain.workspace_productivity import (
    ProductivityCommand,
    RecordPage,
    WorkspaceRecordDenied,
    WorkspaceStoreLink,
)
from coeus.services.workspace_productivity import WorkspaceProductivityService

ACTOR = SimpleNamespace(user_id=uuid4())
UNIT, SOURCE = uuid4(), uuid4()
NOW = "2026-08-04T12:00:00+00:00"


class _Store:
    def __init__(self, *pages: RecordPage[WorkspaceStoreLink]) -> None:
        self._pages = list(pages)
        self.saved: ProductivityCommand | None = None
        self.cursors: list[UUID | None] = []

    def list_store_links(self, *args: object) -> RecordPage[WorkspaceStoreLink]:
        self.cursors.append(args[4])  # type: ignore[arg-type]
        return self._pages.pop(0) if self._pages else RecordPage((), None)

    def save_store_link(self, command: ProductivityCommand) -> ProductivityCommand:
        self.saved = command
        return command


class _StoreDetails:
    def __init__(self, titles: dict[UUID, str]) -> None:
        self._titles = titles

    def get_visible_product(self, _actor: object, product_id: UUID) -> SimpleNamespace:
        if product_id not in self._titles:
            raise AppError(404, "not_found", "Product was not found.")
        return SimpleNamespace(metadata=SimpleNamespace(title=self._titles[product_id]))


class _StoreProjects:
    def __init__(self, names: dict[UUID, str]) -> None:
        self._names = names

    def get_for_member(self, _user_id: UUID, project_id: UUID) -> SimpleNamespace:
        if project_id not in self._names:
            raise AppError(404, "not_found", "Project was not found.")
        return SimpleNamespace(name=self._names[project_id])


def _link(target_id: UUID, target_type: str = "product") -> WorkspaceStoreLink:
    return WorkspaceStoreLink(
        uuid4(), ACTOR.user_id, UNIT, "ticket", SOURCE, target_type, target_id, "stale", 1, NOW
    )


def _service(
    store: _Store,
    titles: dict[UUID, str] | None = None,
    names: dict[UUID, str] | None = None,
    *,
    wired: bool = True,
) -> WorkspaceProductivityService:
    return WorkspaceProductivityService(
        store,  # type: ignore[arg-type]
        _StoreDetails(titles or {}) if wired else None,  # type: ignore[arg-type]
        _StoreProjects(names or {}) if wired else None,  # type: ignore[arg-type]
    )


def _list(service: WorkspaceProductivityService, limit: int = 10) -> RecordPage[WorkspaceStoreLink]:
    return service.list_store_links(ACTOR, UNIT, "ticket", SOURCE, None, limit)  # type: ignore[arg-type]


def test_links_are_relabelled_from_the_live_record() -> None:
    product, project = uuid4(), uuid4()
    store = _Store(RecordPage((_link(product), _link(project, "project")), None))
    service = _service(store, {product: "Regional assessment"}, {project: "Regional project"})

    page = _list(service)

    assert [item.label for item in page.items] == ["Regional assessment", "Regional project"]
    assert page.next_cursor is None


def test_a_link_the_reader_can_no_longer_open_disappears() -> None:
    visible, hidden = uuid4(), uuid4()
    store = _Store(RecordPage((_link(hidden), _link(visible)), None))
    service = _service(store, {visible: "Regional assessment"})

    page = _list(service)

    assert [item.target_id for item in page.items] == [visible]


def test_paging_follows_the_store_cursor_until_the_page_is_full() -> None:
    first = [uuid4() for _ in range(2)]
    second = [uuid4() for _ in range(2)]
    store = _Store(
        RecordPage(tuple(_link(value) for value in first), first[-1]),
        RecordPage(tuple(_link(value) for value in second), None),
    )
    titles = {value: f"Report {index}" for index, value in enumerate([*first, *second])}
    service = _service(store, titles)

    page = _list(service, limit=3)

    assert len(page.items) == 3
    assert page.next_cursor == page.items[2].link_id
    assert store.cursors == [None, first[-1]]


def test_an_unwired_store_hides_the_link_rather_than_showing_a_stale_label() -> None:
    product = uuid4()
    unwired = _Store(RecordPage((_link(product),), None))
    assert _list(_service(unwired, {product: "Regional"}, wired=False)).items == ()


def test_saving_a_link_stamps_the_current_label_rather_than_trusting_the_caller() -> None:
    product = uuid4()
    store = _Store()
    service = _service(store, {product: "Regional assessment"})
    command = ProductivityCommand(
        uuid4(),
        "key-1",
        ACTOR.user_id,
        "save_store_link",
        {"target_type": "product", "target_id": product, "label": "Anything I like"},
    )

    service.save_store_link(ACTOR, command)  # type: ignore[arg-type]

    assert store.saved is not None
    assert store.saved.payload["label"] == "Regional assessment"


def test_saving_a_link_to_an_unreadable_record_is_refused() -> None:
    store = _Store()
    service = _service(store)
    command = ProductivityCommand(
        uuid4(),
        "key-1",
        ACTOR.user_id,
        "save_store_link",
        {"target_type": "product", "target_id": uuid4()},
    )

    with pytest.raises(WorkspaceRecordDenied):
        service.save_store_link(ACTOR, command)  # type: ignore[arg-type]
    assert store.saved is None
