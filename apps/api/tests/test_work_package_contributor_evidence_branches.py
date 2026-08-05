"""Account, posting, participant and replay contributor evidence branches."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import Connection

from coeus.domain.jioc_principals import JIOC_AGENT_PRINCIPAL
from coeus.domain.work_package_contributors import (
    ChangeContributorCommand,
    ContributorChangeRequest,
    ContributorOperation,
    WorkPackageContributorConflict,
    WorkPackageContributorDenied,
    contributor_change_hash,
)
from coeus.persistence.work_package_contributors_postgres import (
    _participant_active,
    _replay,
    _validate_account_and_posting,
)

NOW = datetime(2026, 8, 4, 8, tzinfo=UTC)


class _Result:
    def __init__(self, rows: tuple[Any, ...] = ()) -> None:
        self.rows = rows

    def mappings(self) -> "_Result":
        return self

    def first(self) -> Any:
        return self.rows[0] if self.rows else None

    def __iter__(self) -> Iterator[Any]:
        return iter(self.rows)


class _Connection:
    def __init__(self, *results: _Result) -> None:
        self.results = list(results)

    def execute(self, *_args: object, **_kwargs: object) -> _Result:
        return self.results.pop(0)


def _request(**changes: object) -> ContributorChangeRequest:
    request = ContributorChangeRequest(
        uuid4(),
        uuid4(),
        uuid4(),
        ContributorOperation.ADD,
        1,
        2,
        uuid4(),
        3,
        uuid4(),
        4,
        5,
        "a" * 64,
    )
    return replace(request, **changes)  # type: ignore[arg-type]


def test_account_and_single_home_posting_guards() -> None:
    request = _request(contributor_user_id=JIOC_AGENT_PRINCIPAL)
    with pytest.raises(WorkPackageContributorDenied, match="human"):
        _validate_account_and_posting(cast(Connection, _Connection()), request, NOW)
    request = _request()
    valid = {
        "is_active": True,
        "roles": ["Analyst"],
        "credential_version": request.expected_account_credential_version,
        "source_hash": request.expected_account_source_hash,
    }
    invalid_accounts = (
        None,
        {**valid, "is_active": False},
        {**valid, "roles": ["Customer"]},
        {**valid, "credential_version": 99},
        {**valid, "source_hash": "b" * 64},
    )
    for account in invalid_accounts:
        rows = () if account is None else (account,)
        with pytest.raises(WorkPackageContributorDenied, match="account evidence"):
            _validate_account_and_posting(
                cast(Connection, _Connection(_Result(rows))), request, NOW
            )
    membership = {
        "membership_id": request.membership_id,
        "unit_id": request.unit_id,
        "version": request.expected_membership_version,
    }
    for memberships in ((), (membership, membership)):
        with pytest.raises(WorkPackageContributorDenied, match="exactly one"):
            _validate_account_and_posting(
                cast(Connection, _Connection(_Result((valid,)), _Result(memberships))),
                request,
                NOW,
            )
    for changed in (
        {"membership_id": uuid4()},
        {"unit_id": uuid4()},
        {"version": 99},
    ):
        with pytest.raises(WorkPackageContributorDenied, match="posting evidence"):
            _validate_account_and_posting(
                cast(
                    Connection,
                    _Connection(_Result((valid,)), _Result(({**membership, **changed},))),
                ),
                request,
                NOW,
            )
    _validate_account_and_posting(
        cast(Connection, _Connection(_Result((valid,)), _Result((membership,)))),
        request,
        NOW,
    )


def test_participant_state_and_replay_collisions() -> None:
    request, actor = _request(), uuid4()
    command = ChangeContributorCommand(
        uuid4(), "evidence-branches", actor, request, contributor_change_hash(actor, request)
    )
    assert not _participant_active(cast(Connection, _Connection(_Result())), request)
    assert _participant_active(cast(Connection, _Connection(_Result(({"active": True},)))), request)
    assert _replay(cast(Connection, _Connection(_Result())), command) is None
    stored = {
        "request_hash": contributor_change_hash(actor, request),
        "actor_user_id": actor,
        "package_id": request.package_id,
        "contributor_user_id": request.contributor_user_id,
        "operation": request.operation.value,
        "result_package_version": 2,
        "result_active": True,
    }
    with pytest.raises(WorkPackageContributorConflict, match="identities"):
        _replay(cast(Connection, _Connection(_Result((stored, stored)))), command)
    with pytest.raises(WorkPackageContributorConflict, match="identity was reused"):
        _replay(
            cast(Connection, _Connection(_Result(({**stored, "operation": "end"},)))),
            command,
        )
    result = _replay(cast(Connection, _Connection(_Result((stored,)))), command)
    assert result is not None and result.replayed and result.contributor_active
