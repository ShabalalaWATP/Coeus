"""Application policy over the integrated workspace operations store."""

from types import SimpleNamespace
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.domain.workspace_operations import (
    WorkspacePerson,
    WorkspaceScope,
    WorkspaceSearchResult,
)
from coeus.services.workspace_operations import WorkspaceOperationsService

UNIT = uuid4()
ACTOR = SimpleNamespace(user_id=uuid4())


class _Store:
    def __init__(
        self,
        people: tuple[WorkspacePerson, ...] = (),
        results: tuple[WorkspaceSearchResult, ...] = (),
    ) -> None:
        self._people = people
        self._results = results
        self.requested_limit: int | None = None

    def people(self, *_args: object) -> tuple[WorkspacePerson, ...]:
        return self._people

    def search(self, *args: object) -> tuple[WorkspaceSearchResult, ...]:
        self.requested_limit = int(str(args[4]))
        return self._results


class _Users:
    def __init__(self, accounts: dict[UUID, SimpleNamespace]) -> None:
        self._accounts = accounts

    def get_user(self, user_id: UUID) -> SimpleNamespace | None:
        return self._accounts.get(user_id)


class _StoreDetails:
    def __init__(self, titles: dict[UUID, str]) -> None:
        self._titles = titles

    def get_visible_product(self, _actor: object, product_id: UUID) -> SimpleNamespace:
        if product_id not in self._titles:
            raise AppError(404, "not_found", "Product was not found.")
        return SimpleNamespace(metadata=SimpleNamespace(title=self._titles[product_id]))


class _StoreProjects:
    def __init__(self, projects: tuple[SimpleNamespace, ...] = ()) -> None:
        self._projects = projects

    def get_for_member(self, _user_id: UUID, project_id: UUID) -> SimpleNamespace:
        for project in self._projects:
            if project.project_id == project_id:
                return project
        raise AppError(404, "not_found", "Project was not found.")

    def list_for_user(self, _user_id: UUID) -> tuple[SimpleNamespace, ...]:
        return self._projects


class _StoreSearch:
    def __init__(self, hits: tuple[SimpleNamespace, ...] = (), fails: bool = False) -> None:
        self._hits = hits
        self._fails = fails

    def search(self, _actor: object, _filters: object) -> SimpleNamespace:
        if self._fails:
            raise AppError(422, "invalid_query", "Search terms are invalid.")
        return SimpleNamespace(hits=self._hits)


def _service(
    store: _Store,
    users: dict[UUID, SimpleNamespace] | None = None,
    titles: dict[UUID, str] | None = None,
    projects: tuple[SimpleNamespace, ...] = (),
    store_search: _StoreSearch | None = None,
) -> WorkspaceOperationsService:
    return WorkspaceOperationsService(
        store,  # type: ignore[arg-type]
        _Users(users or {}),  # type: ignore[arg-type]
        _StoreDetails(titles or {}),  # type: ignore[arg-type]
        _StoreProjects(projects),  # type: ignore[arg-type]
        store_search or _StoreSearch(),  # type: ignore[arg-type]
    )


def _person(user_id: UUID, minutes: int | None, zone: str | None) -> WorkspacePerson:
    return WorkspacePerson(user_id, "member", True, zone, minutes)


def _account(name: str, username: str, active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(display_name=name, username=username, is_active=active)


def test_people_drop_unknown_and_inactive_accounts_and_sort_by_display_name() -> None:
    known, inactive, missing = uuid4(), uuid4(), uuid4()
    store = _Store(
        people=(
            _person(missing, 2_220, "Europe/London"),
            _person(inactive, 2_220, "Europe/London"),
            _person(known, 2_220, "Europe/London"),
        )
    )
    service = _service(
        store,
        users={
            known: _account("Zoe Analyst", "zoe@example.test"),
            inactive: _account("Adam Former", "adam@example.test", active=False),
        },
    )

    people = service.people(ACTOR.user_id, UNIT, WorkspaceScope.DIRECT, None, 10)

    assert tuple(item.user_id for item in people) == (known,)
    assert people[0].working_pattern == "37h per week · Europe/London"


def test_people_search_matches_display_name_or_username_and_respects_the_limit() -> None:
    first, second, third = uuid4(), uuid4(), uuid4()
    store = _Store(
        people=(
            _person(first, 2_220, "Europe/London"),
            _person(second, 2_250, "Europe/London"),
            _person(third, 2_220, "Europe/London"),
        )
    )
    service = _service(
        store,
        users={
            first: _account("Ada Lovelace", "ada@example.test"),
            second: _account("Grace Hopper", "grace@example.test"),
            third: _account("Someone Else", "ada.deputy@example.test"),
        },
    )

    by_name = service.people(ACTOR.user_id, UNIT, WorkspaceScope.DIRECT, " Ada ", 10)
    bounded = service.people(ACTOR.user_id, UNIT, WorkspaceScope.DIRECT, None, 2)

    assert {item.display_name for item in by_name} == {"Ada Lovelace", "Someone Else"}
    assert [item.display_name for item in bounded] == ["Ada Lovelace", "Grace Hopper"]
    # An unknown working pattern is stated rather than guessed.
    assert by_name[0].working_pattern == "37h per week · Europe/London"
    assert bounded[1].working_pattern == "37h 30m per week · Europe/London"


def test_a_person_without_a_pattern_or_zone_says_so() -> None:
    user_id = uuid4()
    store = _Store(people=(_person(user_id, None, None),))
    service = _service(store, users={user_id: _account("Pat Analyst", "pat@example.test")})

    people = service.people(ACTOR.user_id, UNIT, WorkspaceScope.DIRECT, None, 10)

    assert people[0].working_pattern == "Working pattern unavailable"


def test_search_relabels_live_records_and_drops_ones_the_actor_cannot_see() -> None:
    visible_product, hidden_product = uuid4(), uuid4()
    project_id, person_id, hidden_person = uuid4(), uuid4(), uuid4()
    store = _Store(
        results=(
            WorkspaceSearchResult("store_product", visible_product, UNIT, "stale", "Store"),
            WorkspaceSearchResult("store_product", hidden_product, UNIT, "stale", "Store"),
            WorkspaceSearchResult("store_project", project_id, UNIT, "stale", "Store"),
            WorkspaceSearchResult("person", person_id, UNIT, str(person_id), "Person"),
            WorkspaceSearchResult("person", hidden_person, UNIT, str(hidden_person), "Person"),
            WorkspaceSearchResult("team", UNIT, UNIT, "Maritime Team", "MAR"),
        )
    )
    service = _service(
        store,
        users={person_id: _account("Maritime Analyst", "mar@example.test")},
        titles={visible_product: "Maritime assessment"},
        projects=(SimpleNamespace(project_id=project_id, name="Maritime project", archived=False),),
    )

    results = service.search(ACTOR, UNIT, WorkspaceScope.DIRECT, "Maritime", 10)

    assert [item.label for item in results] == [
        "Maritime assessment",
        "Maritime project",
        "Maritime Analyst",
        "Maritime Team",
    ]
    # The store is asked for headroom so that filtered rows can be replaced.
    assert store.requested_limit == 20


def test_search_pages_through_resolved_results() -> None:
    ids = [uuid4() for _ in range(4)]
    store = _Store(
        results=tuple(
            WorkspaceSearchResult("team", value, UNIT, f"Team {index}", "SYN")
            for index, value in enumerate(ids)
        )
    )
    service = _service(store)

    first = service.search(ACTOR, UNIT, WorkspaceScope.DIRECT, "Team", 2)
    second = service.search(ACTOR, UNIT, WorkspaceScope.DIRECT, "Team", 2, offset=2)

    assert [item.label for item in first] == ["Team 0", "Team 1"]
    assert [item.label for item in second] == ["Team 2", "Team 3"]


def test_store_only_search_skips_the_workspace_and_lists_authorised_store_records() -> None:
    product_id, project_id, archived_id = uuid4(), uuid4(), uuid4()
    store = _Store(results=(WorkspaceSearchResult("team", UNIT, UNIT, "Maritime Team", "MAR"),))
    service = _service(
        store,
        projects=(
            SimpleNamespace(project_id=project_id, name="Maritime project", archived=False),
            SimpleNamespace(project_id=archived_id, name="Maritime archive", archived=True),
            SimpleNamespace(project_id=uuid4(), name="Unrelated project", archived=False),
        ),
        store_search=_StoreSearch(
            hits=(
                SimpleNamespace(
                    product=SimpleNamespace(
                        product_id=product_id,
                        reference="PRD-1",
                        metadata=SimpleNamespace(title="Maritime assessment"),
                    )
                ),
            )
        ),
    )

    results = service.search(ACTOR, UNIT, WorkspaceScope.DIRECT, "Maritime", 10, store_only=True)

    assert store.requested_limit is None
    assert [item.result_type for item in results] == ["store_product", "store_project"]
    assert [item.label for item in results] == ["Maritime assessment", "Maritime project"]


def test_store_only_search_survives_a_refused_product_search() -> None:
    project_id = uuid4()
    service = _service(
        _Store(),
        projects=(SimpleNamespace(project_id=project_id, name="Maritime project", archived=False),),
        store_search=_StoreSearch(fails=True),
    )

    results = service.search(ACTOR, UNIT, WorkspaceScope.DIRECT, "Maritime", 10, store_only=True)

    assert [item.object_id for item in results] == [project_id]
