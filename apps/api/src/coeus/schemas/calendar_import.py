"""Admin HTTP contracts for the legacy-calendar import."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CalendarImportFindingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    legacy_entry_id: UUID = Field(serialization_alias="legacyEntryId")
    blocking: bool


class CalendarImportPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    preview_hash: str = Field(serialization_alias="previewHash")
    source_digest: str = Field(serialization_alias="sourceDigest")
    state_digest: str = Field(serialization_alias="stateDigest")
    source_count: int = Field(serialization_alias="sourceCount")
    importable_count: int = Field(serialization_alias="importableCount")
    existing_count: int = Field(serialization_alias="existingCount")
    findings: list[CalendarImportFindingResponse]


class CalendarImportCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    command_id: UUID = Field(alias="commandId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    preview_hash: str = Field(alias="previewHash", pattern=r"^[0-9a-f]{64}$")


class CalendarImportResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    command_id: UUID = Field(serialization_alias="commandId")
    imported_count: int = Field(serialization_alias="importedCount")
    existing_count: int = Field(serialization_alias="existingCount")
    replayed: bool
