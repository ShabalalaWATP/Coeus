"""Organisation mode and cutover evidence rules in the runtime security gate."""

import pytest

from coeus.core.config import Settings
from coeus.domain.jioc_routing import ROUTING_RELATIONAL_CAPACITY_RELEASE, ROUTING_RELEASE
from test_runtime_security_config import valid_dev_settings


@pytest.mark.parametrize("mode", ("shadow", "management", "active"))
def test_organisation_modes_require_postgres(mode: str) -> None:
    settings = Settings(
        environment="local",
        organisation_mode=mode,
        persistence_provider="memory",
    )

    with pytest.raises(ValueError, match="require PostgreSQL persistence"):
        settings.require_runtime_security()


def test_disabled_organisation_mode_remains_local_first() -> None:
    Settings(
        environment="local",
        organisation_mode="disabled",
        persistence_provider="memory",
    ).require_runtime_security()


def test_shadow_organisation_mode_is_allowed_with_postgres() -> None:
    Settings(
        environment="local",
        organisation_mode="shadow",
        persistence_provider="postgres",
    ).require_runtime_security()


def test_management_organisation_mode_is_allowed_with_postgres() -> None:
    Settings(
        environment="local",
        organisation_mode="management",
        persistence_provider="postgres",
    ).require_runtime_security()


def test_management_organisation_mode_requires_relational_tickets() -> None:
    settings = Settings(
        environment="local",
        organisation_mode="management",
        persistence_provider="postgres",
        ticket_persistence_mode="shadow_validate",
    )

    with pytest.raises(ValueError, match="requires relational ticket persistence"):
        settings.require_runtime_security()


def test_active_organisation_mode_fails_closed_with_postgres() -> None:
    """Active authority needs the approved cutover evidence, not just the mode.

    Naming the mode is never sufficient: the immutable candidate digest, its
    source revision and the approved relational capacity release must all be
    present, so an operator cannot switch authority on by configuration alone.
    """
    settings = Settings(
        environment="local",
        organisation_mode="active",
        persistence_provider="postgres",
    )

    with pytest.raises(ValueError) as refused:
        settings.require_runtime_security()

    message = str(refused.value)
    assert "COEUS_ORGANISATION_ACTIVE_CANDIDATE_HASH is required in active mode." in message
    assert "COEUS_ORGANISATION_CUTOVER_SOURCE_REVISION is required in active mode." in message
    assert "relational capacity release before active organisation mode is enabled" in message


def test_a_hosted_environment_must_state_a_non_disabled_organisation_mode() -> None:
    # The rule only applies once a mode beyond "disabled" is in play, so an
    # inherited default cannot silently enable organisation authority.
    inherited = valid_dev_settings(
        persistence_provider="postgres", ticket_persistence_mode="relational"
    )
    object.__setattr__(inherited, "organisation_mode", "shadow")
    inherited.model_fields_set.discard("organisation_mode")

    with pytest.raises(ValueError, match="COEUS_ORGANISATION_MODE must be explicit when hosted"):
        inherited.require_runtime_security()

    valid_dev_settings(
        organisation_mode="shadow",
        persistence_provider="postgres",
        ticket_persistence_mode="relational",
    ).require_runtime_security()


def test_active_mode_accepts_a_complete_approved_cutover() -> None:
    Settings(
        environment="local",
        organisation_mode="active",
        persistence_provider="postgres",
        organisation_active_candidate_hash="a" * 64,
        organisation_cutover_source_revision="release-2026.08",
        jioc_routing_approved_releases=[ROUTING_RELEASE, ROUTING_RELATIONAL_CAPACITY_RELEASE],
    ).require_runtime_security()


@pytest.mark.parametrize(
    ("field", "fragment"),
    [
        ("organisation_active_candidate_hash", "ACTIVE_CANDIDATE_HASH is required"),
        ("organisation_cutover_source_revision", "CUTOVER_SOURCE_REVISION is required"),
    ],
)
def test_each_piece_of_active_cutover_evidence_is_required(field: str, fragment: str) -> None:
    values: dict[str, object] = {
        "environment": "local",
        "organisation_mode": "active",
        "persistence_provider": "postgres",
        "organisation_active_candidate_hash": "a" * 64,
        "organisation_cutover_source_revision": "release-2026.08",
        "jioc_routing_approved_releases": [ROUTING_RELEASE, ROUTING_RELATIONAL_CAPACITY_RELEASE],
    }
    values[field] = None

    with pytest.raises(ValueError, match=fragment):
        Settings(**values).require_runtime_security()  # type: ignore[arg-type]
