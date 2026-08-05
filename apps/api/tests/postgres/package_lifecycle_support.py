"""Shared PostgreSQL fixture helpers for package lifecycle evidence."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from coeus.domain.work_package_contributors import (
    ContributorChangeRequest,
    ContributorOperation,
)
from postgres.work_package_handover_support import (
    insert_handover_evidence,
    upgrade_handover_schema,
)

API_ROOT = Path(__file__).resolve().parents[2]


def lifecycle_fixture(database_url: str):  # type: ignore[no-untyped-def]
    """Create pre-0042 evidence, then prove the lifecycle migration upgrade."""
    upgrade_handover_schema(database_url)
    evidence = insert_handover_evidence(database_url)
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return evidence


def contributor_request(
    evidence,  # type: ignore[no-untyped-def]
    operation: ContributorOperation,
    version: int,
    plan=None,  # type: ignore[no-untyped-def]
) -> ContributorChangeRequest:
    """Bind a contributor command to the fixture's current authority evidence."""
    return ContributorChangeRequest(
        evidence.unit_id,
        evidence.package_id,
        evidence.target_id,
        operation,
        version,
        2,
        evidence.request.authorising_grant_id,
        evidence.request.expected_grant_version,
        evidence.request.target_membership_id,
        evidence.request.expected_target_membership_version,
        evidence.request.expected_target_account_credential_version,
        evidence.request.expected_target_account_source_hash,
        plan,
    )
