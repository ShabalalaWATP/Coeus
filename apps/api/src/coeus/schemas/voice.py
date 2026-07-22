from pydantic import BaseModel, ConfigDict, Field


class VoiceModelUpdateRequest(BaseModel):
    model: str
    enabled: bool


class VoiceApiKeyUpdateRequest(BaseModel):
    api_key: str = Field(min_length=10, max_length=4096, validation_alias="apiKey")


class VoiceModelStateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    model: str
    available_models: list[str] = Field(serialization_alias="availableModels")
    enabled: bool
    api_key_configured: bool = Field(serialization_alias="apiKeyConfigured")


class VoiceConnectionTestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    provider: str
    model: str
    message: str
