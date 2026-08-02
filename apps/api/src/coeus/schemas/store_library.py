from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.schemas.store import StoreProductResponse


class PersonalFolderCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class PersonalFolderResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    folder_id: UUID = Field(serialization_alias="id")
    name: str
    created_at: datetime = Field(serialization_alias="createdAt")


class SavedProductRequest(BaseModel):
    folder_id: UUID | None = Field(default=None, validation_alias="folderId")


class SavedProductResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    product: StoreProductResponse
    folder_id: UUID | None = Field(serialization_alias="folderId")
    saved_at: datetime = Field(serialization_alias="savedAt")


class PersonalLibraryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    folders: list[PersonalFolderResponse]
    saved_products: list[SavedProductResponse] = Field(serialization_alias="savedProducts")
    unavailable_count: int = Field(serialization_alias="unavailableCount")
