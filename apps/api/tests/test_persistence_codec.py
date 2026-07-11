from datetime import UTC, datetime
from types import MappingProxyType
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


def test_legacy_role_names_decode_to_the_renamed_roles() -> None:
    user = UserAccount(
        user_id=uuid4(),
        username="legacy@example.test",
        display_name="Legacy Roles",
        roles=frozenset({RoleName.COLLECTION_MANAGER, RoleName.INTELLIGENCE_ANALYST}),
        permissions=frozenset(),
        password_hash="codec-test-hash",  # noqa: S106 - synthetic hash fixture.
        is_active=True,
        clearance_level=2,
    )
    payload = encode_value(user)
    # Rewrite the stored role values to their pre-rename strings, as any
    # payload persisted before the JIOC restructure would hold them.
    legacy = {"CM Manager": "Collection Manager", "Analyst": "Intelligence Analyst"}
    for role in payload["fields"]["roles"]["__frozenset__"]:
        role["value"] = legacy[role["value"]]

    decoded = decode_value(payload)

    assert isinstance(decoded, UserAccount)
    assert decoded.roles == user.roles


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


def test_container_and_scalar_codec_branches_round_trip() -> None:
    payload = MappingProxyType(
        {
            "items": [uuid4(), "plain"],
            "nested": {"when": datetime.now(UTC)},
        }
    )

    encoded = encode_value(payload)
    decoded = decode_value(encoded)

    assert isinstance(decoded, MappingProxyType)
    assert decoded["items"][1] == "plain"
    assert decode_value([{"value": 1}]) == [{"value": 1}]
    assert encode_value({"list": ["value"]}) == {"list": ["value"]}
