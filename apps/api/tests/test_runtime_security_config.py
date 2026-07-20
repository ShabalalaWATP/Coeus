from pathlib import Path

import pytest
from pydantic import ValidationError

from coeus.core.config import DEFAULT_ASSET_TOKEN_SECRET, DEFAULT_SEED_CREDENTIAL, Settings
from coeus.domain.jioc_routing import ROUTING_RELEASE

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def valid_dev_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "allow_dev_seed_users": True,
        "asset_token_secret": "a" * 32,
        "configuration_encryption_key": "e" * 32,
        "csrf_secret": "c" * 32,
        "environment": "dev",
        "jioc_agent_routing_enabled": "disabled",
        "local_seed_credential": "DifferentDevCredential1!",
        "metrics_bearer_token": "m" * 32,
        "secure_cookies": False,
        "session_secret": "s" * 32,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_valid_local_and_dev_configurations_pass() -> None:
    Settings(environment="local").require_runtime_security()
    valid_dev_settings().require_runtime_security()


def test_example_environment_does_not_configure_bedrock_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COEUS_BEDROCK_API_KEY", raising=False)
    settings = Settings(_env_file=REPOSITORY_ROOT / ".env.example")

    assert not settings.bedrock_api_key


def test_hosted_routing_configuration_must_be_explicit() -> None:
    with pytest.raises(ValueError, match="JIOC_AGENT_ROUTING_ENABLED must be explicit"):
        Settings(environment="dev").require_runtime_security()


def test_hosted_active_routing_requires_explicit_release_approval() -> None:
    settings = valid_dev_settings(jioc_agent_routing_enabled="active")

    with pytest.raises(ValueError, match="JIOC_ROUTING_APPROVED_RELEASES must be explicit"):
        settings.require_runtime_security()


@pytest.mark.parametrize("routing_mode", ("active", "shadow"))
def test_hosted_routing_requires_transactional_ticket_persistence(routing_mode: str) -> None:
    settings = valid_dev_settings(
        jioc_agent_routing_enabled=routing_mode,
        jioc_routing_approved_releases=[ROUTING_RELEASE],
        persistence_provider="memory",
        ticket_persistence_mode="legacy",
    )

    with pytest.raises(ValueError, match="PostgreSQL relational ticket persistence"):
        settings.require_runtime_security()


def test_hosted_advisory_egress_requires_provider_and_data_release() -> None:
    settings = valid_dev_settings(
        llm_provider="gemini_api",
        gemini_api_key="synthetic-key",
        search_planner_remote_enabled=True,
    )

    with pytest.raises(ValueError) as error:
        settings.require_runtime_security()

    assert "ADVISORY_APPROVED_PROVIDERS" in str(error.value)
    assert "ADVISORY_APPROVED_DATA_CLASSIFICATIONS" in str(error.value)


def test_hosted_litellm_requires_an_environment_key_and_https() -> None:
    with pytest.raises(ValueError) as missing:
        valid_dev_settings(llm_provider="litellm_proxy").require_runtime_security()
    assert "COEUS_LITELLM_API_KEY is required" in str(missing.value)
    assert "must use HTTPS" in str(missing.value)

    valid_dev_settings(
        llm_provider="litellm_proxy",
        litellm_api_key="sk-virtual-key",
        litellm_base_url="https://llm.example.test/proxy",
    ).require_runtime_security()


def test_remote_routing_critic_requires_a_safe_outbox_lease() -> None:
    settings = valid_dev_settings(
        llm_provider="gemini_api",
        gemini_api_key="synthetic-key",
        routing_critic_remote_enabled=True,
        advisory_approved_providers=["gemini_api"],
        advisory_approved_data_classifications=["synthetic"],
        llm_api_timeout_seconds=10,
        outbox_lease_seconds=15,
    )

    with pytest.raises(ValueError, match="OUTBOX_LEASE_SECONDS"):
        settings.require_runtime_security()


def test_default_database_url_uses_windows_safe_ipv4_loopback() -> None:
    assert "@127.0.0.1:" in Settings(environment="test").database_url


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        (
            Settings(environment="dev"),
            "Seed users are local/test only.",
        ),
        (
            valid_dev_settings(session_secret=None),
            "COEUS_SESSION_SECRET must be at least 32 characters.",
        ),
        (
            valid_dev_settings(configuration_encryption_key=None),
            "COEUS_CONFIGURATION_ENCRYPTION_KEY is required",
        ),
        (
            Settings(environment="local", configuration_encryption_key="short"),
            "COEUS_CONFIGURATION_ENCRYPTION_KEY must be at least 32 characters",
        ),
        (
            Settings(environment="local", metrics_bearer_token="x" * 5),
            "COEUS_METRICS_BEARER_TOKEN must be at least 32 characters",
        ),
        (
            valid_dev_settings(llm_provider="gemini_api", gemini_api_key=None),
            "COEUS_GEMINI_API_KEY is required",
        ),
        (
            Settings(environment="local", csrf_header_name="X-Other-CSRF"),
            "COEUS_CSRF_HEADER_NAME must remain X-CSRF-Token.",
        ),
        (
            Settings(environment="local", object_storage_provider="gcs"),
            "COEUS_OBJECT_STORAGE_PROVIDER must remain local",
        ),
        (
            Settings(environment="local", pubsub_enabled=True),
            "COEUS_PUBSUB_ENABLED must remain false",
        ),
        (
            Settings(environment="local", session_max_per_user=6, session_max_entries=5),
            "COEUS_SESSION_MAX_PER_USER cannot exceed COEUS_SESSION_MAX_ENTRIES",
        ),
    ],
)
def test_each_runtime_security_rule_group_is_enforced(settings: Settings, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        settings.require_runtime_security()


def test_smtp_requirements_are_enforced_directly() -> None:
    settings = Settings(environment="local", email_provider="smtp")

    with pytest.raises(ValueError) as error:
        settings.require_runtime_security()

    assert "COEUS_SMTP_HOST is required" in str(error.value)
    assert "COEUS_SMTP_FROM is required" in str(error.value)


def test_hosted_smtp_requires_starttls() -> None:
    settings = valid_dev_settings(
        email_provider="smtp",
        smtp_host="smtp.example.test",
        smtp_from="noreply@example.test",
        smtp_starttls=False,
    )

    with pytest.raises(ValueError, match="COEUS_SMTP_STARTTLS must be true"):
        settings.require_runtime_security()


@pytest.mark.parametrize(
    "origin",
    ("*", "ftp://example.test", "https://user@example.test", "https://example.test/path"),
)
def test_credentialed_cors_rejects_unsafe_origins(origin: str) -> None:
    with pytest.raises(ValueError, match="COEUS_ALLOWED_CORS_ORIGINS"):
        Settings(environment="local", allowed_cors_origins=[origin]).require_runtime_security()


def test_proxy_count_requires_trusted_networks() -> None:
    with pytest.raises(ValueError, match="COEUS_TRUSTED_PROXY_CIDRS"):
        Settings(environment="local", trusted_proxy_count=1).require_runtime_security()


def test_proxy_networks_must_be_valid() -> None:
    with pytest.raises(ValueError, match="invalid IP network"):
        Settings(
            environment="local", trusted_proxy_cidrs=["not-a-network"]
        ).require_runtime_security()


def test_runtime_errors_are_aggregated_in_stable_rule_order() -> None:
    settings = Settings(
        environment="dev",
        allow_dev_seed_users=True,
        local_seed_credential=DEFAULT_SEED_CREDENTIAL,
        session_secret=None,
        csrf_secret=None,
        asset_token_secret=DEFAULT_ASSET_TOKEN_SECRET,
        llm_provider="gemini_api",
        csrf_header_name="X-Wrong",
        object_storage_provider="gcs",
        pubsub_enabled=True,
    )

    with pytest.raises(ValueError) as error:
        settings.require_runtime_security()

    message = str(error.value)
    ordered_fragments = (
        "COEUS_LOCAL_SEED_CREDENTIAL",
        "COEUS_CONFIGURATION_ENCRYPTION_KEY",
        "COEUS_SESSION_SECRET",
        "COEUS_CSRF_SECRET",
        "COEUS_ASSET_TOKEN_SECRET",
        "COEUS_METRICS_BEARER_TOKEN",
        "COEUS_GEMINI_API_KEY",
        "COEUS_CSRF_HEADER_NAME",
        "COEUS_OBJECT_STORAGE_PROVIDER",
        "COEUS_PUBSUB_ENABLED",
    )
    positions = [message.index(fragment) for fragment in ordered_fragments]
    assert positions == sorted(positions)


@pytest.mark.parametrize(
    ("field", "value"),
    (("login_lockout_threshold", 0), ("login_lockout_seconds", 0)),
)
def test_lockout_controls_must_be_positive(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(environment="test", **{field: value})  # type: ignore[arg-type]
