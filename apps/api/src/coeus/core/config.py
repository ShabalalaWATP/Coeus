from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentName = Literal["local", "dev", "staging", "prod", "test"]
LlmProviderName = Literal["mock", "gemma_vertex", "gemma_vllm"]
ObjectStorageProviderName = Literal["local", "gcs"]
SEED_USER_ENVIRONMENTS = frozenset({"local", "test"})
SECURE_COOKIE_ENVIRONMENTS = frozenset({"staging", "prod"})


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
    login_attempt_max_entries: int = Field(default=10_000, ge=1)
    registration_max_pending: int = Field(default=500, ge=1)
    audit_log_max_events: int = Field(default=10_000, ge=1)
    argon2_time_cost: int = 2
    argon2_memory_cost: int = 19_456
    argon2_parallelism: int = 1
    local_seed_credential: str = "CoeusLocal1!"
    allow_dev_seed_users: bool = False
    gcp_project_id: str | None = None
    gcp_region: str = "europe-west2"
    llm_provider: LlmProviderName = "mock"
    gemma_vertex_project_id: str | None = None
    gemma_vertex_location: str = "europe-west2"
    gemma_vertex_model: str = "gemma-4-31b"
    object_storage_provider: ObjectStorageProviderName = "local"
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
        if self.environment in {"dev", "staging", "prod"}:
            if not self.session_secret or len(self.session_secret) < 32:
                errors.append("COEUS_SESSION_SECRET must be at least 32 characters.")
            if not self.csrf_secret or len(self.csrf_secret) < 32:
                errors.append("COEUS_CSRF_SECRET must be at least 32 characters.")
        if self.environment in SECURE_COOKIE_ENVIRONMENTS and not self.secure_cookies:
            errors.append(
                "Secure cookies are required for staging/prod environments. "
                "Set COEUS_SECURE_COOKIES=true."
            )
        if errors:
            raise ValueError(" ".join(errors))
