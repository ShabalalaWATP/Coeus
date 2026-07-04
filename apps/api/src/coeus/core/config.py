from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentName = Literal["local", "dev", "staging", "prod", "test"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COEUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: EnvironmentName = "local"
    database_url: str = "postgresql+asyncpg://coeus:coeus-local@localhost:5432/coeus"
    allowed_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    log_level: str = "INFO"
