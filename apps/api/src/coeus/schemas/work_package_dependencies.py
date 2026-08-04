"""HTTP contracts for reviewed work-package dependency commands."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.work_package_dependencies import DependencyOperation


class DependencyChangePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    predecessor_package_id: UUID = Field(alias="predecessorPackageId")
    operation: DependencyOperation
    expected_package_version: int = Field(alias="expectedPackageVersion", ge=1)
    expected_predecessor_version: int = Field(alias="expectedPredecessorVersion", ge=1)
    expected_ownership_version: int = Field(alias="expectedOwnershipVersion", ge=1)
    authorising_grant_id: UUID = Field(alias="authorisingGrantId")
    expected_grant_version: int = Field(alias="expectedGrantVersion", ge=1)


class DependencyChangePreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    preview_hash: str = Field(serialization_alias="previewHash")
    package_id: UUID = Field(serialization_alias="packageId")
    package_version: int = Field(serialization_alias="packageVersion")
    predecessor_package_id: UUID = Field(serialization_alias="predecessorPackageId")
    predecessor_package_version: int = Field(serialization_alias="predecessorPackageVersion")
    ownership_version: int = Field(serialization_alias="ownershipVersion")
    dependency_active: bool = Field(serialization_alias="dependencyActive")
    planned_package_version: int = Field(serialization_alias="plannedPackageVersion")


class ChangeDependencyCommandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    command_id: UUID = Field(alias="commandId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    request: DependencyChangePayload
    preview_hash: str = Field(alias="previewHash", pattern=r"^[0-9a-f]{64}$")


class DependencyChangeResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_id: UUID = Field(serialization_alias="packageId")
    package_version: int = Field(serialization_alias="packageVersion")
    predecessor_package_id: UUID = Field(serialization_alias="predecessorPackageId")
    dependency_active: bool = Field(serialization_alias="dependencyActive")
    replayed: bool
