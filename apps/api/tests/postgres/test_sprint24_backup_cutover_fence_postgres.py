"""Cutover authority remains fenced throughout coordinated restore promotion."""

from pathlib import Path

import psycopg
import pytest
from backup_restore_database_support import dsn, seed_fixture

from coeus.persistence.postgres_logical_backup import security_authority_fence
from coeus.services.coordinated_restore import create_backup_bundle

pytestmark = pytest.mark.postgres


def test_security_fence_blocks_cutover_release_writes_until_promotion(
    postgres_database_url: str, tmp_path: Path
) -> None:
    seed_fixture(postgres_database_url)
    manifest = create_backup_bundle(
        postgres_database_url,
        tmp_path / "source-objects",
        tmp_path / "bundle",
        confirm_quiesced=True,
    )
    with (
        security_authority_fence(postgres_database_url, manifest.tables),
        psycopg.connect(dsn(postgres_database_url)) as writer,
    ):
        writer.execute("SET statement_timeout='250ms'")
        with pytest.raises(psycopg.errors.QueryCanceled):
            writer.execute("UPDATE organisation_cutover_release SET version=version+1")
