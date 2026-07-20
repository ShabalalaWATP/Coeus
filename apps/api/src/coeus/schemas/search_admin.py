from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SearchEmbeddingKeyRequest(BaseModel):
    api_key: str = Field(min_length=10, max_length=4_096, validation_alias="apiKey")


class SearchEmbeddingConfigurationRequest(BaseModel):
    provider: str = Field(min_length=2, max_length=32)
    model: str = Field(min_length=2, max_length=128)
    confirm_external_egress: bool = Field(
        default=False,
        validation_alias="confirmExternalEgress",
    )


class SearchEmbeddingStateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    dimensions: int
    api_key_configured: bool = Field(serialization_alias="apiKeyConfigured")
    available_providers: list[str] = Field(serialization_alias="availableProviders")
    available_models: list[str] = Field(serialization_alias="availableModels")
    index_status: str = Field(serialization_alias="indexStatus")
    index_generation: int = Field(serialization_alias="indexGeneration")
    product_count: int = Field(serialization_alias="productCount")
    chunk_count: int = Field(serialization_alias="chunkCount")
    ticket_count: int = Field(serialization_alias="ticketCount")
    failed_asset_count: int = Field(serialization_alias="failedAssetCount")
    corpus_version: str = Field(serialization_alias="corpusVersion")
    space_id: str = Field(serialization_alias="spaceId")
    changed_by: str | None = Field(serialization_alias="changedBy")
    changed_at: datetime | None = Field(serialization_alias="changedAt")
    last_indexed_at: datetime | None = Field(serialization_alias="lastIndexedAt")
    degraded_reason: str | None = Field(serialization_alias="degradedReason")
    release_id: str = Field(serialization_alias="releaseId")
    evaluation_status: str = Field(serialization_alias="evaluationStatus")
    definitive_no_match_enabled: bool = Field(serialization_alias="definitiveNoMatchEnabled")


class SearchEmbeddingTestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    provider: str
    model: str
    message: str
