import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

import pytest

from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.tickets import WorkflowPlanUpdate
from coeus.persistence.codec import CodecWriteFormat, decode_value, encode_value
from coeus.persistence.codec_registry import ENUM_IDENTITIES, TYPE_IDENTITIES


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


def test_default_writer_uses_stable_ids_and_reader_retains_legacy_compatibility() -> None:
    update = WorkflowPlanUpdate(
        update_id=uuid4(),
        ticket_id=uuid4(),
        title="Preserve codec compatibility",
        owner_role="JIOC",
        status="in_progress",
        note="Reader-first rollout",
        created_at=datetime.now(UTC),
    )

    legacy = encode_value(update, write_format=CodecWriteFormat.LEGACY)
    stable = encode_value(update)

    assert legacy["__type__"] == "coeus.domain.tickets.WorkflowPlanUpdate"
    assert "__type_id__" not in legacy
    assert stable["__type_id__"] == "tickets.workflow_plan_update"
    assert "__type__" not in stable
    assert decode_value(legacy) == update
    assert decode_value(stable) == update


def test_stable_writer_uses_semantic_enum_ids_recursively() -> None:
    user = UserAccount(
        user_id=uuid4(),
        username="stable@example.test",
        display_name="Stable Identity",
        roles=frozenset({RoleName.ADMINISTRATOR}),
        permissions=frozenset({Permission.SYSTEM_CONFIGURE}),
        password_hash="codec-test-hash",  # noqa: S106 - synthetic hash fixture.
        is_active=True,
        clearance_level=3,
    )

    payload = encode_value(user, write_format=CodecWriteFormat.STABLE)

    role = payload["fields"]["roles"]["__frozenset__"][0]
    permission = payload["fields"]["permissions"]["__frozenset__"][0]
    assert payload["__type_id__"] == "auth.user_account"
    assert role["__enum_id__"] == "auth.role_name"
    assert permission["__enum_id__"] == "core.permission"
    assert decode_value(payload) == user


@pytest.mark.parametrize("kind", ["type", "enum"])
def test_ambiguous_persistence_identities_fail_closed(kind: str) -> None:
    payload = {
        f"__{kind}__": "legacy.value",
        f"__{kind}_id__": "stable.value",
        "fields": {},
        "value": "unused",
    }

    with pytest.raises(ValueError, match="exactly one identity format"):
        decode_value(payload)


def test_complete_codec_identity_registry_matches_committed_golden() -> None:
    fixture_path = (
        Path(__file__).parents[3]
        / "packages"
        / "test-fixtures"
        / "persistence-codec-identities.json"
    )
    golden = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload = {
        "types": {
            stable_id: f"{python_type.__module__}.{python_type.__name__}"
            for python_type, stable_id in TYPE_IDENTITIES
        },
        "enums": {
            stable_id: f"{python_type.__module__}.{python_type.__name__}"
            for python_type, stable_id in ENUM_IDENTITIES
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    assert len(TYPE_IDENTITIES) == golden["typeCount"]
    assert len(ENUM_IDENTITIES) == golden["enumCount"]
    assert sha256(canonical).hexdigest() == golden["sha256"]
