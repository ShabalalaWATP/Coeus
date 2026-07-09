from datetime import UTC, datetime
from uuid import uuid4

import pytest

from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.tickets import WorkflowPlanUpdate
from coeus.persistence.codec import decode_value, encode_value


def test_workflow_plan_update_round_trips() -> None:
    update = WorkflowPlanUpdate(
        update_id=uuid4(),
        ticket_id=uuid4(),
        title="Confirm collection tasking",
        owner_role="Collection Manager",
        status="in_progress",
        note="Awaiting source availability confirmation.",
        created_at=datetime.now(UTC),
    )

    decoded = decode_value(encode_value(update))

    assert decoded == update


def test_retired_workspace_permissions_are_rejected_from_snapshots() -> None:
    user = UserAccount(
        user_id=uuid4(),
        username="admin@example.test",
        display_name="Admin",
        roles=frozenset({RoleName.ADMINISTRATOR}),
        permissions=frozenset({Permission.SYSTEM_CONFIGURE}),
        password_hash="codec-test-hash",  # noqa: S106 - synthetic hash fixture.
        is_active=True,
        clearance_level=3,
    )
    payload = encode_value(user)
    payload["fields"]["permissions"]["__frozenset__"].append(
        {
            "__enum__": "coeus.core.permissions.Permission",
            "value": "project:add_member",
        }
    )

    with pytest.raises(ValueError, match="project:add_member"):
        decode_value(payload)


def test_retired_workspace_records_are_rejected_from_collections() -> None:
    update = WorkflowPlanUpdate(
        update_id=uuid4(),
        ticket_id=uuid4(),
        title="Confirm collection tasking",
        owner_role="Collection Manager",
        status="in_progress",
        note="Awaiting source availability confirmation.",
        created_at=datetime.now(UTC),
    )
    payload = {
        "__tuple__": [
            {
                "__type__": "coeus.domain.tickets.ProjectPlanUpdate",
                "fields": {"title": "Retired project plan"},
            },
            encode_value(update),
        ]
    }

    with pytest.raises(KeyError, match="ProjectPlanUpdate"):
        decode_value(payload)
