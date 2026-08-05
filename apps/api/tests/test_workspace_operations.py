"""Focused application tests for integrated workspace operations."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from coeus.domain.auth import UserAccount
from coeus.domain.workspace_operations import (
    WorkspacePerson,
    WorkspaceScope,
    WorkspaceSearchResult,
)
from coeus.services.workspace_operations import WorkspaceOperationsService


def _actor() -> UserAccount:
    return UserAccount(uuid4(), "analyst", "Analyst", frozenset(), frozenset(), "hash", True, 1)


def test_people_excludes_inactive_accounts_and_bounds_search() -> None:
    actor, unit = _actor(), uuid4()
    visible, inactive = uuid4(), uuid4()
    store = Mock()
    store.people.return_value = (
        WorkspacePerson(visible, "member", True, "Europe/London", 2220),
        WorkspacePerson(inactive, "member", True, "Europe/London", 2220),
    )
    users = Mock()
    users.get_user.side_effect = lambda identifier: (
        SimpleNamespace(display_name="Alpha Analyst", username="alpha", is_active=True)
        if identifier == visible
        else SimpleNamespace(display_name="Inactive", username="inactive", is_active=False)
    )
    service = WorkspaceOperationsService(store, users, Mock(), Mock(), Mock())

    people = service.people(actor.user_id, unit, WorkspaceScope.DIRECT, "alpha", 10)

    assert [person.user_id for person in people] == [visible]
    assert people[0].working_pattern == "37h per week · Europe/London"


def test_store_only_search_never_uses_capped_generic_workspace_results() -> None:
    actor, unit, product_id, project_id = _actor(), uuid4(), uuid4(), uuid4()
    store = Mock()
    store.search.return_value = tuple(
        WorkspaceSearchResult("team", uuid4(), unit, f"Team {index}", "Team")
        for index in range(100)
    )
    product = SimpleNamespace(
        product_id=product_id,
        reference="SYN-1",
        metadata=SimpleNamespace(title="Eastern assessment"),
    )
    store_search = Mock()
    store_search.search.return_value = SimpleNamespace(hits=(SimpleNamespace(product=product),))
    projects = Mock()
    projects.list_for_user.return_value = (
        SimpleNamespace(project_id=project_id, name="Eastern project", archived=False),
    )
    service = WorkspaceOperationsService(store, Mock(), Mock(), projects, store_search)

    results = service.search(actor, unit, WorkspaceScope.DIRECT, "Eastern", 20, store_only=True)

    store.search.assert_not_called()
    assert {result.result_type for result in results} == {"store_product", "store_project"}
    assert {result.object_id for result in results} == {product_id, project_id}


def test_workspace_search_rechecks_saved_store_result_authority() -> None:
    actor, unit, product_id = _actor(), uuid4(), uuid4()
    store = Mock()
    store.search.return_value = (
        WorkspaceSearchResult("store_product", product_id, unit, "Stale", "Linked product"),
    )
    details = Mock()
    details.get_visible_product.return_value = SimpleNamespace(
        metadata=SimpleNamespace(title="Current authorised title")
    )
    store_search = Mock()
    store_search.search.return_value = SimpleNamespace(hits=())
    projects = Mock()
    projects.list_for_user.return_value = ()
    service = WorkspaceOperationsService(store, Mock(), details, projects, store_search)

    results = service.search(actor, unit, WorkspaceScope.DIRECT, "Current", 5)

    assert results[0].label == "Current authorised title"
    details.get_visible_product.assert_called_once_with(actor, product_id)


def test_workspace_command_hash_is_stable_for_equivalent_payloads() -> None:
    from coeus.domain.workspace_operations import WorkspaceCommand

    actor, command_id = uuid4(), uuid4()
    first = WorkspaceCommand(command_id, "key", actor, "operation", {"b": 2, "a": 1})
    second = WorkspaceCommand(command_id, "key", actor, "operation", {"a": 1, "b": 2})
    assert first.request_hash == second.request_hash
