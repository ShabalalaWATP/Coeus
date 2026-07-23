"""Focused legacy and invalid authority branches for user administration."""

from dataclasses import replace

import pytest

from coeus.core.permissions import Permission
from test_user_admin_service import _service


def test_unfenced_internal_user_change_uses_compare_and_swap() -> None:
    service, users, _sessions, audit = _service()
    target = users.get_by_username("user@example.test")
    assert target is not None
    updated = replace(target, display_name="Synthetic Updated User")

    service._apply_and_audit(
        target,
        updated,
        "synthetic_user_updated",
        "synthetic-system",
        {"user_id": str(target.user_id)},
    )

    assert users.get_by_id(target.user_id) == updated
    assert audit.list_events()[-1].event_type == "synthetic_user_updated"


def test_authority_fenced_user_change_requires_an_explicit_permission() -> None:
    service, users, _sessions, _audit = _service()
    actor = users.get_by_username("admin@example.test")
    target = users.get_by_username("user@example.test")
    assert actor is not None and target is not None

    with pytest.raises(ValueError, match="require a permission"):
        service._apply_and_audit(
            target,
            replace(target, display_name="Not persisted"),
            "synthetic_user_updated",
            str(actor.user_id),
            {"user_id": str(target.user_id)},
            actor,
            None,
        )

    assert Permission.USER_ASSIGN_ROLE in actor.permissions
    assert users.get_by_id(target.user_id) == target
