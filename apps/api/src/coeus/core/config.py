from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentName = Literal["local", "dev", "staging", "prod", "test"]
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
    csrf_header_name: str = "X-CSRF-Token"
    login_lockout_threshold: int = 5
    login_lockout_seconds: int = 5 * 60
    login_attempt_max_entries: int = Field(default=10_000, ge=1)
    audit_log_max_events: int = Field(default=10_000, ge=1)
    argon2_time_cost: int = 2
    argon2_memory_cost: int = 19_456
    argon2_parallelism: int = 1
    local_seed_credential: str = "CoeusLocal1!"

    def require_runtime_security(self) -> None:
        errors = []
        if self.environment not in SEED_USER_ENVIRONMENTS:
            errors.append(
                "Seed users are local/test only. Configure persistent user storage "
                f"before running environment={self.environment!r}."
            )
        if self.environment in SECURE_COOKIE_ENVIRONMENTS and not self.secure_cookies:
            errors.append(
                "Secure cookies are required for staging/prod environments. "
                "Set COEUS_SECURE_COOKIES=true."
            )
        if errors:
            raise ValueError(" ".join(errors))
