from ipaddress import ip_network
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from coeus.domain.admission import AdmissionMode

EnvironmentName = Literal["local", "dev", "staging", "prod", "test"]
EmailProviderName = Literal["outbox", "smtp"]
EmbeddingProviderName = Literal["mock", "local", "gemini_api"]
LlmProviderName = Literal["mock", "gemini_api", "openai_api", "vertex_ai", "bedrock"]
ObjectStorageProviderName = Literal["local", "gcs"]
PersistenceProviderName = Literal["memory", "file", "postgres"]
TicketPersistenceMode = Literal["legacy", "shadow_validate", "relational"]
SEED_USER_ENVIRONMENTS = frozenset({"local", "test"})
SECURE_COOKIE_ENVIRONMENTS = frozenset({"staging", "prod"})
HOSTED_ENVIRONMENTS = frozenset({"dev", "staging", "prod"})
DEFAULT_SEED_CREDENTIAL = "CoeusLocal1!"
# Local-only default; startup rejects it outside local/test.
DEFAULT_ASSET_TOKEN_SECRET = "local-only-asset-token-secret-not-for-deploy"  # noqa: S105  # nosec B105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COEUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: EnvironmentName = "local"
    database_url: str = "postgresql+asyncpg://coeus:coeus-local@127.0.0.1:5432/coeus"
    allowed_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    log_level: str = "INFO"
    session_cookie_name: str = "coeus_session"
    session_ttl_seconds: int = 30 * 60
    session_max_per_user: int = Field(default=5, ge=1, le=100)
    session_max_entries: int = Field(default=1_000, ge=1, le=100_000)
    secure_cookies: bool = False
    session_secret: str | None = None
    csrf_secret: str | None = None
    csrf_header_name: str = "X-CSRF-Token"
    login_lockout_threshold: int = Field(default=5, ge=1)
    login_lockout_seconds: int = Field(default=5 * 60, ge=1)
    # Number of trusted reverse proxies in front of the API. 0 (default) means
    # X-Forwarded-For is ignored and the socket peer address is used.
    trusted_proxy_count: int = Field(default=0, ge=0, le=10)
    trusted_proxy_cidrs: list[str] = Field(default_factory=list)
    login_attempt_max_entries: int = Field(default=10_000, ge=1)
    registration_max_pending: int = Field(default=500, ge=1)
    auth_ip_max_attempts: int = Field(default=30, ge=1)
    auth_ip_window_seconds: int = Field(default=300, ge=1)
    auth_ip_max_entries: int = Field(default=10_000, ge=1)
    audit_log_max_events: int = Field(default=10_000, ge=1)
    audit_log_path: str = ".local-data/audit/coeus-audit.jsonl"
    configuration_encryption_key: str | None = None
    configuration_encryption_key_path: str = ".local-data/secrets/configuration.key"
    argon2_time_cost: int = 2
    argon2_memory_cost: int = 19_456
    argon2_parallelism: int = 1
    argon2_max_concurrent: int = Field(default=2, ge=1, le=8)
    local_seed_credential: str = DEFAULT_SEED_CREDENTIAL
    allow_dev_seed_users: bool = False
    gcp_project_id: str | None = None
    gcp_region: str = "europe-west2"
    llm_provider: LlmProviderName = "mock"
    embedding_provider: EmbeddingProviderName = "mock"
    embedding_model_path: str = ".local-data/embedding-models"
    gemini_api_key: str | None = None
    gemini_api_model: str = "gemini-3.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    search_approved_releases: list[str] = Field(default_factory=lambda: ["mock:token-hash-v2:1536"])
    automatic_request_discovery_enabled: bool = True
    active_work_offers_enabled: bool = True
    jioc_agent_routing_enabled: bool = True
    gemini_api_timeout_seconds: int = Field(default=10, ge=1, le=60)
    available_gemini_models: list[str] = Field(
        default_factory=lambda: [
            "gemini-3.5-flash",
            "gemini-3.1-pro-preview",
            "gemma-4-31b-it",
            "gemma-4-26b-a4b-it",
        ],
        min_length=1,
    )
    # Optional secondary LLM providers. Gemini API remains the primary
    # provider; these are opt-in alternatives configured the same way
    # (runtime key via the admin API, or env key plus explicit provider).
    llm_api_timeout_seconds: int = Field(default=10, ge=1, le=60)
    provider_max_concurrent: int = Field(default=4, ge=1, le=32)
    provider_max_calls_per_window: int = Field(default=120, ge=1)
    provider_max_calls_per_principal: int = Field(default=30, ge=1)
    provider_window_seconds: int = Field(default=60, ge=1)
    provider_admission_mode: AdmissionMode = AdmissionMode.PRINCIPAL
    provider_circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    provider_circuit_cooldown_seconds: int = Field(default=30, ge=1, le=600)
    shared_resource_admission_mode: AdmissionMode = AdmissionMode.PRINCIPAL
    search_max_concurrent: int = Field(default=2, ge=1, le=32)
    search_max_concurrent_per_principal: int = Field(default=1, ge=1, le=8)
    ticket_max_retained: int = Field(default=10_000, ge=1)
    ticket_max_retained_per_principal: int = Field(default=50, ge=1)
    ticket_admission_mode: AdmissionMode = AdmissionMode.PRINCIPAL
    outbox_batch_size: int = Field(default=50, ge=1, le=500)
    outbox_poll_seconds: int = Field(default=2, ge=1, le=60)
    outbox_lease_seconds: int = Field(default=60, ge=5, le=600)
    outbox_retry_seconds: int = Field(default=30, ge=1, le=3600)
    outbox_max_attempts: int = Field(default=5, ge=1, le=50)
    openai_api_key: str | None = None
    openai_api_model: str = "gpt-5.6-terra"
    available_openai_models: list[str] = Field(
        default_factory=lambda: ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"],
        min_length=1,
    )
    openai_realtime_model: str = "gpt-realtime-mini"
    available_openai_realtime_models: list[str] = Field(
        default_factory=lambda: ["gpt-realtime-mini"], min_length=1
    )
    openai_realtime_voice: str = "marin"
    voice_session_max_concurrent: int = Field(default=4, ge=1, le=32)
    voice_session_max_per_principal: int = Field(default=1, ge=1, le=4)
    voice_session_ttl_seconds: int = Field(default=10 * 60, ge=60, le=60 * 60)
    vertex_api_key: str | None = None
    vertex_api_model: str = "gemini-2.5-flash"
    available_vertex_models: list[str] = Field(
        default_factory=lambda: ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3-flash"],
        min_length=1,
    )
    bedrock_api_key: str | None = None
    bedrock_region: str = "eu-west-2"
    bedrock_api_model: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"
    available_bedrock_models: list[str] = Field(
        default_factory=lambda: [
            "anthropic.claude-sonnet-4-5-20250929-v1:0",
            "anthropic.claude-haiku-4-5-20251001-v1:0",
        ],
        min_length=1,
    )
    object_storage_provider: ObjectStorageProviderName = "local"
    local_object_storage_path: str = ".local-data/objects"
    local_upload_max_bytes: int = Field(default=50_000_000, ge=1)
    upload_max_concurrent: int = Field(default=2, ge=1, le=32)
    upload_max_concurrent_per_user: int = Field(default=1, ge=1, le=8)
    upload_max_inflight_bytes: int = Field(default=100_000_000, ge=1)
    asset_token_secret: str = DEFAULT_ASSET_TOKEN_SECRET
    persistence_provider: PersistenceProviderName = "postgres"
    ticket_persistence_mode: TicketPersistenceMode = "relational"
    persistence_path: str = ".local-data/state/coeus-state.json"
    # Seed the rich local demo dataset (extra products, demo tickets across the
    # workflow, feedback and calendars). None means "auto": on for local only.
    seed_demo_content: bool | None = None
    email_provider: EmailProviderName = "outbox"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65_535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    smtp_timeout_seconds: int = Field(default=10, ge=1, le=60)
    gcs_product_assets_bucket: str | None = None
    gcs_generated_previews_bucket: str | None = None
    pubsub_enabled: bool = False
    pubsub_topic_prefix: str = "coeus-dev"

    def should_seed_demo(self) -> bool:
        """Whether to load the rich demo dataset; auto-on for local only."""
        if self.seed_demo_content is not None:
            return self.seed_demo_content
        return self.environment == "local"

    def require_runtime_security(self) -> None:
        errors = [
            *_seed_user_errors(self),
            *_secret_errors(self),
            *_integration_errors(self),
            *_transport_errors(self),
            *_identity_errors(self),
            *_local_runtime_errors(self),
        ]
        if errors:
            raise ValueError(" ".join(errors))


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
    return tuple(errors)


_LLM_KEY_ENV_VARS = {
    "gemini_api": "COEUS_GEMINI_API_KEY",
    "openai_api": "COEUS_OPENAI_API_KEY",
    "vertex_ai": "COEUS_VERTEX_API_KEY",
    "bedrock": "COEUS_BEDROCK_API_KEY",
}


def _llm_env_key(settings: Settings) -> str | None:
    return {
        "gemini_api": settings.gemini_api_key,
        "openai_api": settings.openai_api_key,
        "vertex_ai": settings.vertex_api_key,
        "bedrock": settings.bedrock_api_key,
    }.get(settings.llm_provider)


def _integration_errors(settings: Settings) -> tuple[str, ...]:
    errors: list[str] = []
    if (
        settings.llm_provider != "mock"
        and not _llm_env_key(settings)
        and settings.environment in HOSTED_ENVIRONMENTS
    ):
        env_var = _LLM_KEY_ENV_VARS[settings.llm_provider]
        errors.append(f"{env_var} is required when COEUS_LLM_PROVIDER={settings.llm_provider}.")
    if settings.email_provider == "smtp":
        if not settings.smtp_host:
            errors.append("COEUS_SMTP_HOST is required when COEUS_EMAIL_PROVIDER=smtp.")
        if not settings.smtp_from:
            errors.append("COEUS_SMTP_FROM is required when COEUS_EMAIL_PROVIDER=smtp.")
        if settings.environment in HOSTED_ENVIRONMENTS and not settings.smtp_starttls:
            errors.append("COEUS_SMTP_STARTTLS must be true outside local/test.")
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
    if settings.session_max_per_user > settings.session_max_entries:
        return ("COEUS_SESSION_MAX_PER_USER cannot exceed COEUS_SESSION_MAX_ENTRIES.",)
    return ()


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
