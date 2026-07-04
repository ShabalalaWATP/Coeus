from fastapi import Request

from coeus.api.dependencies import get_readiness_checker, get_request_id
from coeus.core.config import Settings
from coeus.db.session import DatabaseReadinessChecker


def test_get_readiness_checker_uses_configured_database_url() -> None:
    checker = get_readiness_checker(
        Settings(environment="test", database_url="postgresql+asyncpg://example")
    )

    assert isinstance(checker, DatabaseReadinessChecker)
    assert checker.database_url == "postgresql+asyncpg://example"


def test_get_request_id_returns_unknown_when_state_has_no_request_id() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})

    assert get_request_id(request) == "unknown"
