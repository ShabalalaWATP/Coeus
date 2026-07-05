import pytest

from coeus.db import session
from coeus.db.session import DatabaseReadinessChecker


class FakeConnection:
    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback) -> None:
        return None

    async def execute(self, statement) -> None:
        self.statement = statement


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    def connect(self) -> FakeConnection:
        return FakeConnection()

    async def dispose(self) -> None:
        self.disposed = True


@pytest.mark.asyncio
async def test_database_readiness_checker_handles_invalid_url() -> None:
    checker = DatabaseReadinessChecker("not-a-valid-sqlalchemy-url")

    result = await checker.check()

    assert result.ready is False
    assert result.detail == "database connectivity failed"


@pytest.mark.asyncio
async def test_database_readiness_checker_returns_ready_for_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine = FakeEngine()
    monkeypatch.setattr(session, "create_async_engine", lambda *_args, **_kwargs: fake_engine)

    result = await DatabaseReadinessChecker("postgresql+asyncpg://example").check()

    assert result.ready is True
    assert result.detail == "database reachable"
    assert fake_engine.disposed is True


@pytest.mark.asyncio
async def test_database_readiness_checker_handles_unexpected_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_unexpected_error(*_args, **_kwargs) -> None:
        raise RuntimeError("driver unavailable")

    monkeypatch.setattr(session, "create_async_engine", raise_unexpected_error)

    result = await DatabaseReadinessChecker("postgresql+asyncpg://example").check()

    assert result.ready is False
    assert result.detail == "database readiness check failed"
