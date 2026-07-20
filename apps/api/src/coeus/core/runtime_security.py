"""Runtime deployment validation, kept separate from settings declaration."""

from ipaddress import ip_network
from urllib.parse import urlsplit

from coeus.core.advisory_egress import HOSTED_ENVIRONMENTS, advisory_egress_errors
from coeus.core.config import DEFAULT_ASSET_TOKEN_SECRET, DEFAULT_SEED_CREDENTIAL, Settings
from coeus.core.litellm_endpoint import litellm_base_url_errors
from coeus.domain.jioc_routing import ROUTING_RELEASE, JiocRoutingMode, normalise_routing_mode

SEED_USER_ENVIRONMENTS = frozenset({"local", "test"})
SECURE_COOKIE_ENVIRONMENTS = frozenset({"staging", "prod"})
_LLM_KEY_ENV_VARS = {
    "gemini_api": "COEUS_GEMINI_API_KEY",
    "openai_api": "COEUS_OPENAI_API_KEY",
    "litellm_proxy": "COEUS_LITELLM_API_KEY",
    "vertex_ai": "COEUS_VERTEX_API_KEY",
    "bedrock": "COEUS_BEDROCK_API_KEY",
}


def runtime_security_errors(settings: Settings) -> tuple[str, ...]:
    return (
        *_seed_user_errors(settings),
        *_secret_errors(settings),
        *_integration_errors(settings),
        *advisory_egress_errors(settings),
        *_transport_errors(settings),
        *_identity_errors(settings),
        *_local_runtime_errors(settings),
    )


def _seed_user_errors(settings: Settings) -> tuple[str, ...]:
    dev_seed_users_allowed = settings.environment == "dev" and settings.allow_dev_seed_users
    errors: list[str] = []
    if settings.environment not in SEED_USER_ENVIRONMENTS and not dev_seed_users_allowed:
        errors.append(
            "Seed users are local/test only. Configure persistent user storage "
            f"before running environment={settings.environment!r}."
        )
    if dev_seed_users_allowed and settings.local_seed_credential == DEFAULT_SEED_CREDENTIAL:
        errors.append(
            "COEUS_LOCAL_SEED_CREDENTIAL must be overridden with a non-default value "
            "when dev seed users are enabled, otherwise the published default password "
            "grants administrator access."
        )
    return tuple(errors)


def _secret_errors(settings: Settings) -> tuple[str, ...]:
    errors: list[str] = []
    if (
        settings.configuration_encryption_key is not None
        and len(settings.configuration_encryption_key) < 32
    ):
        errors.append("COEUS_CONFIGURATION_ENCRYPTION_KEY must be at least 32 characters.")
    if settings.metrics_bearer_token is not None and len(settings.metrics_bearer_token) < 32:
        errors.append("COEUS_METRICS_BEARER_TOKEN must be at least 32 characters.")
    if settings.environment not in HOSTED_ENVIRONMENTS:
        return tuple(errors)
    if not settings.configuration_encryption_key:
        errors.append("COEUS_CONFIGURATION_ENCRYPTION_KEY is required in hosted environments.")
    if not settings.session_secret or len(settings.session_secret) < 32:
        errors.append("COEUS_SESSION_SECRET must be at least 32 characters.")
    if not settings.csrf_secret or len(settings.csrf_secret) < 32:
        errors.append("COEUS_CSRF_SECRET must be at least 32 characters.")
    if (
        settings.asset_token_secret == DEFAULT_ASSET_TOKEN_SECRET
        or len(settings.asset_token_secret) < 32
    ):
        errors.append("COEUS_ASSET_TOKEN_SECRET must be a non-default secret.")
    if settings.metrics_bearer_token is None:
        errors.append("COEUS_METRICS_BEARER_TOKEN is required in hosted environments.")
    return tuple(errors)


def _llm_env_key(settings: Settings) -> str | None:
    return {
        "gemini_api": settings.gemini_api_key,
        "openai_api": settings.openai_api_key,
        "litellm_proxy": settings.litellm_api_key,
        "vertex_ai": settings.vertex_api_key,
        "bedrock": settings.bedrock_api_key,
    }.get(settings.llm_provider)


def _integration_errors(settings: Settings) -> tuple[str, ...]:
    errors: list[str] = []
    hosted = settings.environment in HOSTED_ENVIRONMENTS
    if settings.llm_provider != "mock" and not _llm_env_key(settings) and hosted:
        env_var = _LLM_KEY_ENV_VARS[settings.llm_provider]
        errors.append(f"{env_var} is required when COEUS_LLM_PROVIDER={settings.llm_provider}.")
    if settings.llm_provider == "litellm_proxy":
        errors.extend(litellm_base_url_errors(settings.litellm_base_url, hosted=hosted))
    if settings.email_provider == "smtp":
        if not settings.smtp_host:
            errors.append("COEUS_SMTP_HOST is required when COEUS_EMAIL_PROVIDER=smtp.")
        if not settings.smtp_from:
            errors.append("COEUS_SMTP_FROM is required when COEUS_EMAIL_PROVIDER=smtp.")
        if hosted and not settings.smtp_starttls:
            errors.append("COEUS_SMTP_STARTTLS must be true outside local/test.")
    routing_mode = normalise_routing_mode(settings.jioc_agent_routing_enabled)
    if hosted and "jioc_agent_routing_enabled" not in settings.model_fields_set:
        errors.append("COEUS_JIOC_AGENT_ROUTING_ENABLED must be explicit when hosted.")
    if (
        routing_mode is JiocRoutingMode.ACTIVE
        and (hosted or settings.jioc_agent_routing_enabled is True)
        and "jioc_routing_approved_releases" not in settings.model_fields_set
    ):
        errors.append("COEUS_JIOC_ROUTING_APPROVED_RELEASES must be explicit for this active mode.")
    if (
        routing_mode is JiocRoutingMode.ACTIVE
        and ROUTING_RELEASE not in settings.jioc_routing_approved_releases
    ):
        errors.append(
            "COEUS_JIOC_ROUTING_APPROVED_RELEASES must contain the current evaluated "
            f"routing release ({ROUTING_RELEASE}) before active routing is enabled."
        )
    return tuple(errors)


def _transport_errors(settings: Settings) -> tuple[str, ...]:
    errors: list[str] = []
    if settings.csrf_header_name != "X-CSRF-Token":
        errors.append("COEUS_CSRF_HEADER_NAME must remain X-CSRF-Token.")
    if settings.environment in SECURE_COOKIE_ENVIRONMENTS and not settings.secure_cookies:
        errors.append(
            "Secure cookies are required for staging/prod environments. "
            "Set COEUS_SECURE_COOKIES=true."
        )
    if settings.trusted_proxy_count and not settings.trusted_proxy_cidrs:
        errors.append(
            "COEUS_TRUSTED_PROXY_CIDRS is required when COEUS_TRUSTED_PROXY_COUNT is non-zero."
        )
    for cidr in settings.trusted_proxy_cidrs:
        try:
            ip_network(cidr, strict=False)
        except ValueError:
            errors.append("COEUS_TRUSTED_PROXY_CIDRS contains an invalid IP network.")
            break
    for origin in settings.allowed_cors_origins:
        parsed = urlsplit(origin)
        if (
            origin == "*"
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            errors.append(
                "COEUS_ALLOWED_CORS_ORIGINS must contain only absolute HTTP(S) origins "
                "without wildcards, credentials, paths, queries, or fragments."
            )
            break
    return tuple(errors)


def _identity_errors(settings: Settings) -> tuple[str, ...]:
    error = "COEUS_SESSION_MAX_PER_USER cannot exceed COEUS_SESSION_MAX_ENTRIES."
    return (error,) if settings.session_max_per_user > settings.session_max_entries else ()


def _local_runtime_errors(settings: Settings) -> tuple[str, ...]:
    errors: list[str] = []
    if settings.object_storage_provider != "local":
        errors.append(
            "COEUS_OBJECT_STORAGE_PROVIDER must remain local until the future GCS adapter "
            "and migration gates are implemented."
        )
    if settings.pubsub_enabled:
        errors.append(
            "COEUS_PUBSUB_ENABLED must remain false until the future worker adapter and "
            "migration gates are implemented."
        )
    return tuple(errors)
