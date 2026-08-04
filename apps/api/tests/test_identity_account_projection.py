"""The relational account projection retains eligibility evidence only."""

from dataclasses import replace
from typing import Any, cast
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection

from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.jioc_principals import JIOC_AGENT_PRINCIPAL
from coeus.persistence.codec import encode_value
from coeus.persistence.identity_account_projection import (
    active_human_analyst_account,
    identity_projection_rows,
)


def _user() -> UserAccount:
    return UserAccount(
        user_id=uuid4(),
        username="analyst@example.test",
        display_name="Synthetic Analyst",
        roles=frozenset({RoleName.INTELLIGENCE_ANALYST}),
        permissions=frozenset(),
        password_hash="secret-hash",  # noqa: S106  # nosec B106 - non-authentic test value
        is_active=True,
        clearance_level=3,
        credential_version=4,
    )


def test_projection_excludes_credentials_and_profile_content() -> None:
    user = _user()
    rows = identity_projection_rows({"users": [encode_value(user)]})
    assert rows[0]["user_id"] == user.user_id
    assert rows[0]["roles"] == [RoleName.INTELLIGENCE_ANALYST.value]
    assert rows[0]["is_active"] is True
    assert "password" not in str(rows[0]).casefold()
    assert user.username not in str(rows[0])
    assert user.display_name not in str(rows[0])


def test_projection_rejects_malformed_or_duplicate_snapshots() -> None:
    user = _user()
    with pytest.raises(ValueError, match="users list"):
        identity_projection_rows({})
    with pytest.raises(ValueError, match="unsupported"):
        identity_projection_rows({"users": [{}]})
    with pytest.raises(ValueError, match="duplicate"):
        identity_projection_rows(
            {"users": [encode_value(user), encode_value(replace(user, username="duplicate"))]}
        )


def test_active_human_analyst_account_fails_closed_and_can_lock() -> None:
    connection = MagicMock()
    assert (
        active_human_analyst_account(cast(Connection, connection), JIOC_AGENT_PRINCIPAL, lock=True)
        is None
    )
    connection.execute.assert_not_called()

    result = connection.execute.return_value.mappings.return_value
    result.first.side_effect = (
        None,
        {"is_active": False, "roles": ["Analyst"]},
        {"is_active": True, "roles": ["Administrator"]},
        {
            "user_id": _user().user_id,
            "is_active": True,
            "roles": ["Analyst"],
            "credential_version": 4,
            "source_hash": "a" * 64,
        },
    )
    human_id = uuid4()
    assert active_human_analyst_account(cast(Connection, connection), human_id, lock=False) is None
    assert active_human_analyst_account(cast(Connection, connection), human_id, lock=True) is None
    assert active_human_analyst_account(cast(Connection, connection), human_id, lock=True) is None
    account = active_human_analyst_account(cast(Connection, connection), human_id, lock=True)
    assert cast(dict[str, Any], account)["credential_version"] == 4
    assert "FOR UPDATE" in str(connection.execute.call_args.args[0])
