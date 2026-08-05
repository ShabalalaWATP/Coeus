"""Bounded PostgreSQL serialisation retry behaviour."""

import pytest
from sqlalchemy.exc import OperationalError

from coeus.persistence.serializable_retry import retry_serializable_once


class _DatabaseError(Exception):
    def __init__(self, sqlstate: str) -> None:
        self.sqlstate = sqlstate


def _error(sqlstate: str) -> OperationalError:
    return OperationalError("SELECT 1", {}, _DatabaseError(sqlstate))


def test_returns_first_success_without_retry() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    assert retry_serializable_once(operation) == "ok"
    assert calls == 1


def test_retries_one_serialisation_failure() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _error("40001")
        return "ok"

    assert retry_serializable_once(operation) == "ok"
    assert calls == 2


def test_does_not_retry_other_or_second_database_failure() -> None:
    with pytest.raises(OperationalError):
        retry_serializable_once(lambda: (_ for _ in ()).throw(_error("23505")))
    calls = 0

    def always_serialization_failure() -> None:
        nonlocal calls
        calls += 1
        raise _error("40001")

    with pytest.raises(OperationalError):
        retry_serializable_once(always_serialization_failure)
    assert calls == 2
