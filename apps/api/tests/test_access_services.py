import pytest

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.auth import SeedUserRepository
from coeus.services.access import build_access_services
from coeus.services.audit import AuditLog
from coeus.services.passwords import PasswordHasher


def build_seed_access_services():
    settings = Settings(environment="test", argon2_memory_cost=8_192)
    users = SeedUserRepository(settings, PasswordHasher(settings))
    return build_access_services(SeedAccessRepository(users), AuditLog())


def test_customer_product_access_is_filtered_by_acg() -> None:
    services = build_seed_access_services()
    customer = services.repository.list_users()[1]
    products = services.repository.list_products()

    allowed_titles = [
        product.title
        for product in products
        if services.product_policy.evaluate(customer, product).allowed
    ]

    assert allowed_titles == ["Regional Stability Brief"]


def test_product_access_denies_missing_acg_even_with_rbac_permission() -> None:
    services = build_seed_access_services()
    customer = services.repository.list_users()[1]
    collection_product = next(
        product for product in services.repository.list_products() if "Collection" in product.title
    )

    decision = services.product_policy.evaluate(customer, collection_product)

    assert decision.allowed is False
    assert any(check.name == "acg_membership" and not check.passed for check in decision.checks)


def test_draft_products_require_product_management_permission() -> None:
    services = build_seed_access_services()
    customer = services.repository.list_users()[1]
    draft_product = next(
        product
        for product in services.repository.list_products()
        if product.status == ProductStatus.DRAFT
    )

    decision = services.product_policy.evaluate(customer, draft_product)

    assert decision.allowed is False
    assert any(check.name == "draft_visibility" and not check.passed for check in decision.checks)


def test_project_workspace_filters_visible_products() -> None:
    services = build_seed_access_services()
    customer = services.repository.list_users()[1]
    project = services.projects.list_visible_workspaces(customer)[0]

    assert project.project.reference == "PRJ-NORTHSTAR"
    assert [product.title for product in project.visible_products] == ["Regional Stability Brief"]


def test_inactive_acg_no_longer_grants_project_or_product_access() -> None:
    services = build_seed_access_services()
    admin = services.repository.get_user_by_username("admin@example.test")
    rfa_team = services.repository.get_user_by_username("rfa.team@example.test")
    assert admin is not None
    assert rfa_team is not None
    assessment_acg = next(
        acg for acg in services.repository.list_acgs() if acg.code == "ACG-CHARLIE-ASSESSMENT"
    )
    assessment_product = next(
        product for product in services.repository.list_products() if "Draft Pack" in product.title
    )
    project = services.repository.list_projects()[0]

    assert services.product_policy.evaluate(rfa_team, assessment_product).allowed is True
    assert services.project_policy.evaluate(rfa_team, project).allowed is True

    services.acgs.update_acg(admin, assessment_acg.acg_id, is_active=False)

    product_decision = services.product_policy.evaluate(rfa_team, assessment_product)
    project_decision = services.project_policy.evaluate(rfa_team, project)

    assert product_decision.allowed is False
    assert project_decision.allowed is False
    assert any(
        check.name == "acg_membership" and not check.passed for check in product_decision.checks
    )
    assert any(
        check.name == "project_membership" and not check.passed for check in project_decision.checks
    )


def test_administrator_gets_access_diagnostic_override() -> None:
    services = build_seed_access_services()
    admin = services.repository.list_users()[0]
    collection_product = next(
        product for product in services.repository.list_products() if "Collection" in product.title
    )

    decision = services.diagnostics.diagnose_product(collection_product.product_id, admin.user_id)

    assert Permission.PRODUCT_READ_RESTRICTED in admin.permissions
    assert decision.allowed is True


def test_disabled_user_is_denied_project_and_product_access() -> None:
    services = build_seed_access_services()
    disabled = services.repository.get_user_by_username("disabled@example.test")
    assert disabled is not None
    project = services.repository.list_projects()[0]
    product = services.repository.list_products()[0]

    project_decision = services.project_policy.evaluate(disabled, project)
    product_decision = services.product_policy.evaluate(disabled, product)

    assert project_decision.allowed is False
    assert product_decision.allowed is False
    assert services.projects.list_visible_workspaces(disabled) == ()


def test_acg_member_assignment_rejects_missing_user() -> None:
    services = build_seed_access_services()
    admin = services.repository.get_user_by_username("admin@example.test")
    assert admin is not None
    acg = services.repository.list_acgs()[0]

    with pytest.raises(AppError) as exc_info:
        services.acgs.add_user(admin, acg.acg_id, services.repository.list_products()[0].product_id)

    assert exc_info.value.code == "user_not_found"
