"""Idempotency, digest and cursor guards on the synthetic workforce surfaces."""

import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from coeus.domain.my_work import MyWorkCursor, decode_cursor, encode_cursor
from coeus.domain.synthetic_organisation_fixture import SyntheticFixtureCommand
from coeus.domain.team_task_ownership import WorkflowLeg

DIGEST = "b" * 64


def _command(**overrides: object) -> SyntheticFixtureCommand:
    values: dict[str, object] = {
        "command_id": uuid4(),
        "idempotency_key": "synthetic-fixture-1",
        "actor_user_id": uuid4(),
        "preview_hash": DIGEST,
    }
    values.update(overrides)
    return SyntheticFixtureCommand(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("key", ["", " synthetic-fixture-1", "synthetic-fixture-1 "])
def test_an_idempotency_key_must_be_present_and_trimmed(key: str) -> None:
    with pytest.raises(ValueError, match="non-empty and trimmed"):
        _command(idempotency_key=key)


def test_an_idempotency_key_is_bounded() -> None:
    with pytest.raises(ValueError, match="cannot exceed 128 characters"):
        _command(idempotency_key="k" * 129)


def test_an_idempotency_key_rejects_control_characters() -> None:
    with pytest.raises(ValueError, match="control characters"):
        _command(idempotency_key="synthetic\tfixture")


@pytest.mark.parametrize("digest", ["b" * 63, "B" * 64, "z" * 64])
def test_a_preview_hash_must_be_a_lowercase_sha256_digest(digest: str) -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256 digest"):
        _command(preview_hash=digest)


def _cursor(sort_at: str, sort_order: int) -> str:
    payload = json.dumps(
        [sort_at, str(uuid4()), WorkflowLeg.RFA.value, sort_order, str(uuid4())],
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def test_a_my_work_cursor_survives_a_round_trip() -> None:
    cursor = MyWorkCursor(datetime(2026, 8, 5, 9, tzinfo=UTC), uuid4(), WorkflowLeg.RFA, 0, uuid4())

    assert decode_cursor(encode_cursor(cursor)) == cursor


def test_a_naive_cursor_timestamp_is_refused() -> None:
    with pytest.raises(ValueError, match="cursor is invalid"):
        decode_cursor(_cursor("2026-08-05T09:00:00", 0))


def test_a_negative_cursor_sort_order_is_refused() -> None:
    with pytest.raises(ValueError, match="cursor is invalid"):
        decode_cursor(_cursor("2026-08-05T09:00:00+00:00", -1))
