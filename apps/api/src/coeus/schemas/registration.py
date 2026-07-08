from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegistrationSubmitRequest(BaseModel):
    username: str = Field(min_length=6, max_length=254, pattern=EMAIL_PATTERN)
    display_name: str = Field(
        min_length=2,
        max_length=120,
        validation_alias="displayName",
    )
    justification: str = Field(default="", max_length=1_000)
    password: str = Field(min_length=12, max_length=256)


class RegistrationSubmitResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str


class RegistrationDecisionRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class RegistrationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    registration_id: UUID = Field(serialization_alias="id")
    username: str
    display_name: str = Field(serialization_alias="displayName")
    justification: str
    status: str
    created_at: datetime = Field(serialization_alias="createdAt")


class RegistrationListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    registrations: list[RegistrationResponse]


class AiModelSelectRequest(BaseModel):
    model: str = Field(min_length=3, max_length=80)


class AiModelApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=10, max_length=4096, validation_alias="apiKey")


class AiModelStateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    active_model: str = Field(serialization_alias="activeModel")
    available_models: list[str] = Field(serialization_alias="availableModels")
    api_key_configured: bool = Field(serialization_alias="apiKeyConfigured")
    embedding_provider: str = Field(serialization_alias="embeddingProvider")
    embedded_product_count: int = Field(serialization_alias="embeddedProductCount")
    changed_by: str | None = Field(default=None, serialization_alias="changedBy")
    changed_at: datetime | None = Field(default=None, serialization_alias="changedAt")
