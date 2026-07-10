import asyncio
from collections.abc import AsyncIterator
from types import TracebackType

import pytest

from coeus.db import session
from coeus.db.session import DatabaseReadinessChecker, dispose_readiness_engines


class FakeConnection:
    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        return None

    async def execute(self, statement: object) -> None:
        self.statement = statement


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False
        self.connect_calls = 0

    def connect(self) -> FakeConnection:
        self.connect_calls += 1
        return FakeConnection()

    async def dispose(self) -> None:
        self.disposed = True


@pytest.fixture(autouse=True)
async def _reset_engine_cache() -> AsyncIterator[None]:
    await dispose_readiness_engines()
    yield
    await dispose_readiness_engines()


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


@pytest.mark.asyncio
async def test_database_readiness_checker_reuses_cached_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine = FakeEngine()
    created = []

    def build(*_args: object, **_kwargs: object) -> FakeEngine:
        created.append(1)
        return fake_engine

    monkeypatch.setattr(session, "create_async_engine", build)

    checker = DatabaseReadinessChecker("postgresql+asyncpg://example")
    first = await checker.check()
    second = await checker.check()

    assert first.ready is True
    assert second.ready is True
    assert len(created) == 1
    assert fake_engine.connect_calls == 1
    assert fake_engine.disposed is False

    await dispose_readiness_engines()
    assert fake_engine.disposed is True


@pytest.mark.asyncio
async def test_database_readiness_checker_handles_unexpected_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_unexpected_error(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("driver unavailable")

    monkeypatch.setattr(session, "create_async_engine", raise_unexpected_error)

    result = await DatabaseReadinessChecker("postgresql+asyncpg://example").check()

    assert result.ready is False
    assert result.detail == "database readiness check failed"


@pytest.mark.asyncio
async def test_database_readiness_checker_coalesces_concurrent_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine = FakeEngine()
    monkeypatch.setattr(session, "create_async_engine", lambda *_args, **_kwargs: fake_engine)
    checker = DatabaseReadinessChecker("postgresql+asyncpg://example")

    results = await asyncio.gather(*(checker.check() for _ in range(50)))

    assert all(result.ready for result in results)
    assert fake_engine.connect_calls == 1
