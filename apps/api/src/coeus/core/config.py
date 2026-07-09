from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentName = Literal["local", "dev", "staging", "prod", "test"]
EmailProviderName = Literal["outbox", "smtp"]
EmbeddingProviderName = Literal["mock", "local", "gemini_api"]
LlmProviderName = Literal["mock", "gemini_api"]
ObjectStorageProviderName = Literal["local", "gcs"]
PersistenceProviderName = Literal["memory", "file", "postgres"]
SEED_USER_ENVIRONMENTS = frozenset({"local", "test"})
SECURE_COOKIE_ENVIRONMENTS = frozenset({"staging", "prod"})
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
    database_url: str = "postgresql+asyncpg://coeus:coeus-local@localhost:5432/coeus"
    allowed_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    log_level: str = "INFO"
    session_cookie_name: str = "coeus_session"
    session_ttl_seconds: int = 30 * 60
    secure_cookies: bool = False
    session_secret: str | None = None
    csrf_secret: str | None = None
    csrf_header_name: str = "X-CSRF-Token"
    login_lockout_threshold: int = 5
    login_lockout_seconds: int = 5 * 60
    # Number of trusted reverse proxies in front of the API. 0 (default) means
    # X-Forwarded-For is ignored and the socket peer address is used.
    trusted_proxy_count: int = Field(default=0, ge=0, le=10)
    login_attempt_max_entries: int = Field(default=10_000, ge=1)
    registration_max_pending: int = Field(default=500, ge=1)
    auth_ip_max_attempts: int = Field(default=30, ge=1)
    auth_ip_window_seconds: int = Field(default=300, ge=1)
    auth_ip_max_entries: int = Field(default=10_000, ge=1)
    audit_log_max_events: int = Field(default=10_000, ge=1)
    argon2_time_cost: int = 2
    argon2_memory_cost: int = 19_456
    argon2_parallelism: int = 1
    local_seed_credential: str = DEFAULT_SEED_CREDENTIAL
    allow_dev_seed_users: bool = False
    gcp_project_id: str | None = None
    gcp_region: str = "europe-west2"
    llm_provider: LlmProviderName = "mock"
    embedding_provider: EmbeddingProviderName = "mock"
    embedding_model_path: str = ".local-data/embedding-models"
    gemini_api_key: str | None = None
    gemini_api_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_api_timeout_seconds: int = Field(default=10, ge=1, le=60)
    available_gemini_models: list[str] = Field(
        default_factory=lambda: [
            "gemma-4-31b",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-3-flash",
        ],
        min_length=1,
    )
    object_storage_provider: ObjectStorageProviderName = "local"
    local_object_storage_path: str = ".local-data/objects"
    local_upload_max_bytes: int = Field(default=50_000_000, ge=1)
    asset_token_secret: str = DEFAULT_ASSET_TOKEN_SECRET
    persistence_provider: PersistenceProviderName = "postgres"
    persistence_path: str = ".local-data/state/coeus-state.json"
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

    def require_runtime_security(self) -> None:
        errors = []
        dev_seed_users_allowed = self.environment == "dev" and self.allow_dev_seed_users
        if self.environment not in SEED_USER_ENVIRONMENTS and not dev_seed_users_allowed:
            errors.append(
                "Seed users are local/test only. Configure persistent user storage "
                f"before running environment={self.environment!r}."
            )
        if dev_seed_users_allowed and self.local_seed_credential == DEFAULT_SEED_CREDENTIAL:
            errors.append(
                "COEUS_LOCAL_SEED_CREDENTIAL must be overridden with a non-default value "
                "when dev seed users are enabled, otherwise the published default password "
                "grants administrator access."
            )
        if self.environment in {"dev", "staging", "prod"}:
            if not self.session_secret or len(self.session_secret) < 32:
                errors.append("COEUS_SESSION_SECRET must be at least 32 characters.")
            if not self.csrf_secret or len(self.csrf_secret) < 32:
                errors.append("COEUS_CSRF_SECRET must be at least 32 characters.")
            if (
                self.asset_token_secret == DEFAULT_ASSET_TOKEN_SECRET
                or len(self.asset_token_secret) < 32
            ):
                errors.append("COEUS_ASSET_TOKEN_SECRET must be a non-default secret.")
        if (
            self.llm_provider == "gemini_api"
            and not self.gemini_api_key
            and self.environment in {"dev", "staging", "prod"}
        ):
            errors.append("COEUS_GEMINI_API_KEY is required when COEUS_LLM_PROVIDER=gemini_api.")
        if self.csrf_header_name != "X-CSRF-Token":
            errors.append("COEUS_CSRF_HEADER_NAME must remain X-CSRF-Token.")
        if self.email_provider == "smtp":
            if not self.smtp_host:
                errors.append("COEUS_SMTP_HOST is required when COEUS_EMAIL_PROVIDER=smtp.")
            if not self.smtp_from:
                errors.append("COEUS_SMTP_FROM is required when COEUS_EMAIL_PROVIDER=smtp.")
            if self.environment in {"dev", "staging", "prod"} and not self.smtp_starttls:
                errors.append("COEUS_SMTP_STARTTLS must be true outside local/test.")
        if self.environment in SECURE_COOKIE_ENVIRONMENTS and not self.secure_cookies:
            errors.append(
                "Secure cookies are required for staging/prod environments. "
                "Set COEUS_SECURE_COOKIES=true."
            )
        if errors:
            raise ValueError(" ".join(errors))
