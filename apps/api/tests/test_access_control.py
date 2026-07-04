from coeus.core.access_control import require_permission
from coeus.core.permissions import Permission


def test_require_permission_allows_matching_permission() -> None:
    decision = require_permission({Permission.PRODUCT_READ}, Permission.PRODUCT_READ)

    assert decision.allowed is True
    assert decision.reason == "permission_granted"


def test_require_permission_denies_missing_permission() -> None:
    decision = require_permission({Permission.USER_READ_SELF}, Permission.PRODUCT_READ)

    assert decision.allowed is False
    assert decision.reason == "permission_missing"
