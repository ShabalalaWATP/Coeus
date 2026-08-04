"""Idempotent replay identity for organisation grant commands."""

from uuid import UUID, uuid4

import pytest

from coeus.domain.organisation_authority import OrganisationIdempotencyConflict
from coeus.persistence.organisation_authority_postgres import _replay

COMMAND, GRANT, ACTOR = uuid4(), uuid4(), uuid4()
KEY, HASH, TYPE = "grant-1", "a" * 64, "create_grant"


def _row(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "command_id": COMMAND,
        "idempotency_key": KEY,
        "request_hash": HASH,
        "command_type": TYPE,
        "actor_user_id": ACTOR,
        "grant_id": GRANT,
        "result_version": 2,
    }
    values.update(overrides)
    return values


def _replay_row(row: dict[str, object] | None) -> object:
    return _replay(row, COMMAND, KEY, HASH, TYPE, ACTOR, GRANT)  # type: ignore[arg-type]


def test_an_unseen_command_has_nothing_to_replay() -> None:
    assert _replay_row(None) is None


def test_an_identical_command_replays_its_recorded_result() -> None:
    result = _replay_row(_row())

    assert result is not None
    assert (result.grant_id, result.version, result.replayed) == (GRANT, 2, True)


@pytest.mark.parametrize(
    "overrides",
    [
        {"command_id": uuid4()},
        {"idempotency_key": "grant-2"},
        {"request_hash": "b" * 64},
        {"command_type": "revoke_grant"},
        {"actor_user_id": uuid4()},
        {"grant_id": uuid4()},
    ],
)
def test_a_reused_identity_carrying_another_payload_is_refused(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(OrganisationIdempotencyConflict, match="already has another payload"):
        _replay_row(_row(**overrides))


def test_identities_are_compared_as_values_not_as_text() -> None:
    # The stored row may hold text rather than UUID objects.
    row = _row(command_id=str(COMMAND), actor_user_id=str(ACTOR), grant_id=str(GRANT))

    result = _replay_row(row)

    assert result is not None and result.grant_id == GRANT
    assert isinstance(result.grant_id, UUID)
