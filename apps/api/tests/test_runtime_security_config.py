import pytest
from pydantic import ValidationError

from coeus.core.config import DEFAULT_ASSET_TOKEN_SECRET, DEFAULT_SEED_CREDENTIAL, Settings


def valid_dev_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "allow_dev_seed_users": True,
        "asset_token_secret": "a" * 32,
        "csrf_secret": "c" * 32,
        "environment": "dev",
        "local_seed_credential": "DifferentDevCredential1!",
        "secure_cookies": False,
        "session_secret": "s" * 32,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_valid_local_and_dev_configurations_pass() -> None:
    Settings(environment="local").require_runtime_security()
    valid_dev_settings().require_runtime_security()


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
        "COEUS_SESSION_SECRET",
        "COEUS_CSRF_SECRET",
        "COEUS_ASSET_TOKEN_SECRET",
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
