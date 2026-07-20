from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from coeus.core.advisory_egress import (
    HOSTED_ENVIRONMENTS as HOSTED_ENVIRONMENTS,
)
from coeus.domain.admission import AdmissionMode
from coeus.domain.jioc_routing import JiocRoutingMode

EnvironmentName = Literal["local", "dev", "staging", "prod", "test"]
EmailProviderName = Literal["outbox", "smtp"]
EmbeddingProviderName = Literal["mock", "local", "gemini_api"]
LlmProviderName = Literal[
    "mock", "gemini_api", "openai_api", "litellm_proxy", "vertex_ai", "bedrock"
]
ObjectStorageProviderName = Literal["local", "gcs"]
PersistenceProviderName = Literal["memory", "file", "postgres"]
TicketPersistenceMode = Literal["legacy", "shadow_validate", "relational"]
DEFAULT_SEED_CREDENTIAL = "CoeusLocal1!"
APPROVED_JIOC_ROUTING_RELEASE = "jioc-routing-policy-v2:jioc-routing-eval-v2"
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
    metrics_bearer_token: str | None = None
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
    search_planner_remote_enabled: bool = False
    routing_critic_remote_enabled: bool = False
    advisory_approved_providers: list[LlmProviderName] = Field(default_factory=list)
    advisory_approved_data_classifications: list[str] = Field(default_factory=list)
    embedding_provider: EmbeddingProviderName = "mock"
    embedding_model_path: str = ".local-data/embedding-models"
    gemini_api_key: str | None = None
    gemini_api_model: str = "gemini-3.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    search_approved_releases: list[str] = Field(default_factory=lambda: ["mock:token-hash-v2:1536"])
    automatic_request_discovery_enabled: bool = True
    active_work_offers_enabled: bool = True
    jioc_agent_routing_enabled: JiocRoutingMode | bool = JiocRoutingMode.ACTIVE
    jioc_routing_approved_releases: list[str] = Field(
        default_factory=lambda: [APPROVED_JIOC_ROUTING_RELEASE]
    )
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
    litellm_api_key: str | None = None
    litellm_base_url: str = "http://127.0.0.1:4000"
    litellm_api_model: str = "default"
    available_litellm_models: list[str] = Field(default_factory=lambda: ["default"], min_length=1)
    openai_realtime_model: str = "gpt-realtime-2.1"
    available_openai_realtime_models: list[str] = Field(
        default_factory=lambda: ["gpt-realtime-2.1", "gpt-realtime-mini"], min_length=1
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
        if self.seed_demo_content is not None:
            return self.seed_demo_content
        return self.environment == "local"

    def require_runtime_security(self) -> None:
        from coeus.core.runtime_security import runtime_security_errors

        errors = runtime_security_errors(self)
        if errors:
            raise ValueError(" ".join(errors))
