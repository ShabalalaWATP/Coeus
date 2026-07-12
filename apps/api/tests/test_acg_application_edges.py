from dataclasses import replace
from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.access import AccessControlGroup, AcgApplicationStatus
from coeus.main import create_app
from coeus.services.acg_applications import AcgApplicationService


def assert_error(code: str, action: object) -> None:
    with pytest.raises(AppError) as error:
        action()  # type: ignore[operator]
    assert error.value.code == code


def application_context():
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    access = app.state.access_services.repository
    service = app.state.access_services.applications
    customer = access.get_user_by_username("user@example.test")
    colleague = access.get_user_by_username("colleague@example.test")
    admin = access.get_user_by_username("admin@example.test")
    assert customer is not None and colleague is not None and admin is not None
    acg = next(
        item
        for item in access.list_acgs()
        if item.is_active
        and item.acg_id not in access.acg_ids_for_user(customer.user_id)
        and item.acg_id not in access.acg_ids_for_user(colleague.user_id)
    )
    return access, service, customer, colleague, admin, acg


def test_application_service_rejects_invalid_resource_and_actor_edges() -> None:
    access, service, customer, _colleague, admin, acg = application_context()

    assert_error("invalid_justification", lambda: service.submit(customer, acg.acg_id, "short"))
    assert_error(
        "inactive_user",
        lambda: service.catalogue(replace(customer, is_active=False), 1, 20),
    )
    assert_error("forbidden", lambda: service.list_admins(customer, acg.acg_id))
    assert_error("acg_application_not_found", lambda: service.withdraw(customer, acg.acg_id))
    assert_error(
        "acg_application_not_found",
        lambda: service.decide(admin, uuid4(), AcgApplicationStatus.APPROVED, None),
    )

    access.add_membership(acg.acg_id, customer.user_id)
    assert_error(
        "acg_already_member",
        lambda: service.submit(customer, acg.acg_id, "A valid synthetic justification."),
    )
    access.remove_membership(acg.acg_id, customer.user_id)

    inactive_acg = replace(acg, acg_id=uuid4(), code="INACTIVE-EDGE", is_active=False)
    access.save_acg(inactive_acg)
    assert_error(
        "acg_inactive",
        lambda: service.submit(customer, inactive_acg.acg_id, "A valid synthetic justification."),
    )
    assert_error(
        "acg_not_found",
        lambda: service.submit(customer, uuid4(), "A valid synthetic justification."),
    )

    pending = service.submit(customer, acg.acg_id, "A valid synthetic justification.")
    access.add_membership(acg.acg_id, customer.user_id)
    assert_error(
        "acg_already_member",
        lambda: service.decide(admin, pending.application_id, AcgApplicationStatus.APPROVED, None),
    )
    queue, total, pages = service.review_queue(admin, 1, 20)
    assert pending in queue
    assert total >= 1 and pages >= 1


def test_application_and_administrator_changes_roll_back_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _access, service, customer, colleague, admin, acg = application_context()
    audit = service._audit_log
    original_record = audit.record

    def fail_audit(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(audit, "record", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        service.submit(customer, acg.acg_id, "A valid synthetic justification.")
    assert service.own_application(customer, acg.acg_id) is None

    monkeypatch.setattr(audit, "record", original_record)
    pending = service.submit(customer, acg.acg_id, "A valid synthetic justification.")
    monkeypatch.setattr(audit, "record", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        service.withdraw(customer, acg.acg_id)
    assert service.own_application(customer, acg.acg_id) == pending

    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        service.add_admin(admin, acg.acg_id, colleague.user_id)
    assert not service.can_review(colleague, acg.acg_id)

    monkeypatch.setattr(audit, "record", original_record)
    service.add_admin(admin, acg.acg_id, colleague.user_id)
    monkeypatch.setattr(audit, "record", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        service.remove_admin(admin, acg.acg_id, colleague.user_id)
    assert service.can_review(colleague, acg.acg_id)


def test_decision_compensation_restores_membership_and_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    access, service, customer, _colleague, admin, acg = application_context()
    pending = service.submit(customer, acg.acg_id, "A valid synthetic justification.")

    def fail_audit(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(service._audit_log, "record", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        service.decide(admin, pending.application_id, AcgApplicationStatus.APPROVED, None)
    assert acg.acg_id not in access.acg_ids_for_user(customer.user_id)
    assert service.own_application(customer, acg.acg_id) == pending

    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        service.decide(
            admin,
            pending.application_id,
            AcgApplicationStatus.REJECTED,
            "Synthetic rejection reason.",
        )
    assert service.own_application(customer, acg.acg_id) == pending


def test_owner_bootstrap_skips_missing_and_inactive_owners() -> None:
    access, service, customer, _colleague, _admin, _acg = application_context()
    workflows = service._workflows
    missing_owner_acg = AccessControlGroup(
        acg_id=uuid4(),
        code="MISSING-OWNER",
        name="Missing Owner",
        description="Synthetic owner edge.",
        owner_user_id=uuid4(),
        is_active=True,
    )
    inactive_owner_acg = replace(
        missing_owner_acg,
        acg_id=uuid4(),
        code="INACTIVE-OWNER",
        owner_user_id=customer.user_id,
    )
    no_owner_acg = replace(
        missing_owner_acg,
        acg_id=uuid4(),
        code="NO-OWNER",
        owner_user_id=None,
    )
    access.save_acg(missing_owner_acg)
    access.save_acg(inactive_owner_acg)
    access.save_acg(no_owner_acg)
    inactive_customer = replace(customer, is_active=False)
    original_get_user = access.get_user

    def get_user(user_id: object):
        if user_id == customer.user_id:
            return inactive_customer
        return original_get_user(user_id)

    access.get_user = get_user
    AcgApplicationService(access, workflows, service._audit_log)

    assert not workflows.is_initialised(missing_owner_acg.acg_id)
    assert not workflows.is_initialised(inactive_owner_acg.acg_id)
    assert not workflows.is_initialised(no_owner_acg.acg_id)
