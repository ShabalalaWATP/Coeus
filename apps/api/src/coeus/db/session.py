from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


@dataclass(frozen=True)
class ReadinessCheckResult:
    ready: bool
    detail: str


class DatabaseReadinessChecker:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    async def check(self) -> ReadinessCheckResult:
        engine: AsyncEngine | None = None
        try:
            engine = create_async_engine(self.database_url, pool_pre_ping=True)
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return ReadinessCheckResult(ready=False, detail="database connectivity failed")
        except Exception:
            return ReadinessCheckResult(ready=False, detail="database readiness check failed")
        finally:
            if engine is not None:
                await engine.dispose()
        return ReadinessCheckResult(ready=True, detail="database reachable")
