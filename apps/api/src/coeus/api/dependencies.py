from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from coeus.core.config import Settings
from coeus.db.session import DatabaseReadinessChecker


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_readiness_checker(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatabaseReadinessChecker:
    return DatabaseReadinessChecker(settings.database_url)


def get_request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))
