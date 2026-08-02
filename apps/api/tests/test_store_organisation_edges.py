from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from coeus.api.presenters.store_organisation import project_detail, project_summary
from coeus.core.errors import AppError
from coeus.persistence.state_store import MemoryStateStore
from coeus.schemas.store_organisation import (
    ProjectCreateRequest,
    ProjectEntryCreateRequest,
    SubscriptionCriteriaRequest,
)
from coeus.services import store_projects, store_subscriptions
from coeus.services.audit import AuditLog


def _actor() -> Mock:
    actor = Mock()
    actor.user_id = uuid4()
    actor.is_active = True
    return actor


def _project_service(access: Mock | None = None) -> store_projects.StoreProjectService:
    return store_projects.StoreProjectService(MemoryStateStore(), AuditLog(), access or Mock())


def _create(service: store_projects.StoreProjectService, actor: Mock):
    return service.create(
        actor,
        name=" Watch ",
        purpose=" Continuing research ",
        region=" ",
        date_from=None,
        date_to=None,
    )


def test_project_service_rejects_invalid_and_duplicate_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = _actor()
    member = _actor()
    member.username = "member@example.test"
    access = Mock()
    access.get_user_by_username.return_value = member
    service = _project_service(access)
    project = _create(service, actor)

    access.get_user_by_username.return_value = actor
    assert service.add_member(actor, project.project_id, "owner@example.test") == project
    access.get_user_by_username.return_value = None
    with pytest.raises(AppError, match="Active user not found"):
        service.add_member(actor, project.project_id, "missing@example.test")
    with pytest.raises(AppError, match="owner cannot be removed"):
        service.remove_member(actor, project.project_id, actor.user_id)
    with pytest.raises(AppError, match="Project member not found"):
        service.remove_member(actor, project.project_id, uuid4())

    product_id = uuid4()
    with pytest.raises(AppError, match="Project product not found"):
        service.remove_product(actor, project.project_id, product_id)
    with pytest.raises(AppError, match="Enter a note or question"):
        service.add_entry(actor, project.project_id, "note", " ")
    with pytest.raises(AppError, match="Enter a project name"):
        service.create(
            actor, name=" ", purpose="Purpose", region=None, date_from=None, date_to=None
        )

    assert service.add_product(actor, project.project_id, product_id).product_ids == (product_id,)
    assert service.add_product(actor, project.project_id, product_id).product_ids == (product_id,)
    monkeypatch.setattr(store_projects, "MAX_PROJECT_PRODUCTS", 1)
    with pytest.raises(AppError, match="product limit"):
        service.add_product(actor, project.project_id, uuid4())
    monkeypatch.setattr(store_projects, "MAX_PROJECT_ENTRIES", 0)
    with pytest.raises(AppError, match="note limit"):
        service.add_entry(actor, project.project_id, "note", "Bounded note")


def test_project_service_enforces_owner_member_and_project_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = _actor()
    member = _actor()
    access = Mock()
    access.get_user_by_username.return_value = member
    service = _project_service(access)
    project = _create(service, actor)
    project = service.add_member(actor, project.project_id, "member@example.test")

    with pytest.raises(AppError, match="Only the project owner"):
        service.add_member(member, project.project_id, "other@example.test")
    monkeypatch.setattr(store_projects, "MAX_PROJECT_MEMBERS", 2)
    access.get_user_by_username.return_value = _actor()
    with pytest.raises(AppError, match="member limit"):
        service.add_member(actor, project.project_id, "other@example.test")

    monkeypatch.setattr(store_projects, "MAX_OWNED_PROJECTS", 1)
    with pytest.raises(AppError, match="owned project limit"):
        _create(service, actor)
    assert service.list_for_user(member.user_id)[0].project_id == project.project_id
    assert (
        service.get_for_member(member.user_id, project.project_id).project_id == project.project_id
    )
    access.get_user.return_value = member
    assert service.user_account(member.user_id) == member


def test_subscription_validation_conflicts_and_audit_rollback() -> None:
    user_id = uuid4()
    criteria = store_subscriptions.SubscriptionCriteria(query=" regional ")
    service = store_subscriptions.StoreSubscriptionService(MemoryStateStore(), AuditLog())
    first = service.create(user_id, name=" First ", cadence="daily", criteria=criteria)
    second = service.create(
        user_id,
        name="Second",
        cadence="manual",
        criteria=store_subscriptions.SubscriptionCriteria(tag="watch"),
    )
    with pytest.raises(AppError, match="name already exists"):
        service.update(
            user_id,
            second.subscription_id,
            name=first.name,
            cadence="weekly",
            enabled=True,
            criteria=criteria,
        )
    with pytest.raises(AppError, match="Enter a subscription name"):
        service.create(user_id, name=" ", cadence="daily", criteria=criteria)

    state = MemoryStateStore()
    audit = Mock(spec=AuditLog)
    audit.record.side_effect = RuntimeError("audit unavailable")
    rollback = store_subscriptions.StoreSubscriptionService(state, audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        rollback.create(user_id, name="Rollback", cadence="daily", criteria=criteria)
    assert state.load(store_subscriptions.SUBSCRIPTION_NAMESPACE) == {"subscriptions": []}


def test_store_organisation_schemas_reject_invalid_ranges() -> None:
    with pytest.raises(ValidationError, match="dateFrom must be"):
        ProjectCreateRequest(
            name="Watch", purpose="Purpose", dateFrom="2026-12-31", dateTo="2026-01-01"
        )
    with pytest.raises(ValidationError, match="Questions must be"):
        ProjectEntryCreateRequest(kind="question", body="x" * 501)
    with pytest.raises(ValidationError, match="dateFrom must be"):
        SubscriptionCriteriaRequest(dateFrom="2026-12-31", dateTo="2026-01-01")


def test_project_presenter_fails_closed_and_handles_removed_accounts() -> None:
    actor = _actor()
    service = _project_service()
    project = _create(service, actor)
    store = Mock()
    store.projects.user_account.return_value = None
    store.details.get_visible_product.side_effect = AppError(403, "forbidden", "Denied")
    assert project_detail(project, actor, store).members[0].display_name == "Former member"
    restricted = store_projects._replace_project(
        project,
        product_ids=(uuid4(),),
        actor_user_id=actor.user_id,
        action="project_product_added",
    )
    with pytest.raises(AppError, match="Denied"):
        project_summary(restricted, actor, store)
