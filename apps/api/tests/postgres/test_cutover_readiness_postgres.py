"""Real PostgreSQL bounded/fail-closed cutover evidence gate."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from coeus.domain.cutover_readiness import CutoverCheckCode, CutoverCheckStatus
from coeus.persistence.cutover_readiness_postgres import PostgresCutoverReadinessStore

pytestmark = pytest.mark.postgres


def test_empty_head_schema_is_safely_blocked(postgres_database_url: str) -> None:
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_database_url)
    command.upgrade(config, "head")
    checks = PostgresCutoverReadinessStore(create_engine(postgres_database_url)).inspect()
    by_code = {item.code: item for item in checks}
    assert by_code[CutoverCheckCode.MIGRATION_HEAD].status is CutoverCheckStatus.PASSED
    assert by_code[CutoverCheckCode.ORGANISATION_TOPOLOGY].status is CutoverCheckStatus.BLOCKED
    assert by_code[CutoverCheckCode.IDENTITY_PROJECTION].status is CutoverCheckStatus.BLOCKED
    assert len(checks) == 11
