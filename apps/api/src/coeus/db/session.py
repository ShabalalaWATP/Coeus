from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

# Readiness probes run frequently; engines are cached per URL instead of being
# built and disposed on every request. NullPool keeps connections per-call so
# the cached engine is safe to share across event loops.
_ENGINES: dict[str, AsyncEngine] = {}


@dataclass(frozen=True)
class ReadinessCheckResult:
    ready: bool
    detail: str


class DatabaseReadinessChecker:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    async def check(self) -> ReadinessCheckResult:
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


async def dispose_readiness_engines() -> None:
    """Dispose cached readiness engines, e.g. on application shutdown."""
    for engine in _ENGINES.values():
        await engine.dispose()
    _ENGINES.clear()
