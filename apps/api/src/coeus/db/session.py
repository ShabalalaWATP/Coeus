import asyncio
from dataclasses import dataclass
from time import monotonic

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

# Readiness probes run frequently; engines are cached per URL instead of being
# built and disposed on every request. NullPool keeps connections per-call so
# the cached engine is safe to share across event loops.
_ENGINES: dict[str, AsyncEngine] = {}
_CHECKERS: dict[str, "DatabaseReadinessChecker"] = {}


@dataclass(frozen=True)
class ReadinessCheckResult:
    ready: bool
    detail: str


class DatabaseReadinessChecker:
    def __init__(self, database_url: str, cache_seconds: float = 1.0) -> None:
        self.database_url = database_url
        self._cache_seconds = cache_seconds
        self._lock = asyncio.Lock()
        self._cached: tuple[float, ReadinessCheckResult] | None = None

    async def check(self) -> ReadinessCheckResult:
        cached = self._current_cached()
        if cached is not None:
            return cached
        async with self._lock:
            cached = self._current_cached()
            if cached is not None:
                return cached
            result = await self._check_database()
            self._cached = (monotonic(), result)
            return result

    def _current_cached(self) -> ReadinessCheckResult | None:
        if self._cached is None:
            return None
        checked_at, result = self._cached
        return result if monotonic() - checked_at < self._cache_seconds else None

    async def _check_database(self) -> ReadinessCheckResult:
        try:
            engine = _engine_for(self.database_url)
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return ReadinessCheckResult(ready=False, detail="database connectivity failed")
        except Exception:
            return ReadinessCheckResult(ready=False, detail="database readiness check failed")
        return ReadinessCheckResult(ready=True, detail="database reachable")


def _engine_for(database_url: str) -> AsyncEngine:
    engine = _ENGINES.get(database_url)
    if engine is None:
        engine = create_async_engine(database_url, poolclass=NullPool)
        _ENGINES[database_url] = engine
    return engine


def readiness_checker_for(database_url: str) -> DatabaseReadinessChecker:
    checker = _CHECKERS.get(database_url)
    if checker is None:
        checker = DatabaseReadinessChecker(database_url)
        _CHECKERS[database_url] = checker
    return checker


async def dispose_readiness_engines() -> None:
    """Dispose cached readiness engines, e.g. on application shutdown."""
    for engine in _ENGINES.values():
        await engine.dispose()
    _ENGINES.clear()
    _CHECKERS.clear()
