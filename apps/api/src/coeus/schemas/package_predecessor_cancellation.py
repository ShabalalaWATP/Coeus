"""HTTP contracts for explicit predecessor cancellation dispositions."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from coeus.domain.package_predecessor_cancellation import DependantDispositionAction


class DependantDispositionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    dependant_package_id: UUID = Field(alias="dependantPackageId")
    expected_version: int = Field(alias="expectedVersion", ge=1)
    action: DependantDispositionAction
    replacement_package_id: UUID | None = Field(default=None, alias="replacementPackageId")
    expected_replacement_version: int | None = Field(
        default=None, alias="expectedReplacementVersion", ge=1
    )

    @model_validator(mode="after")
    def validate_replacement(self) -> "DependantDispositionPayload":
        replacement = self.replacement_package_id is not None
        if replacement != (self.expected_replacement_version is not None):
            raise ValueError("replacement identity and version must be supplied together")
        if (self.action is DependantDispositionAction.REPLACE) != replacement:
            raise ValueError("only replacement disposition may identify a replacement")
        return self


class PredecessorCancellationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    expected_package_version: int = Field(alias="expectedPackageVersion", ge=1)
    expected_ownership_version: int = Field(alias="expectedOwnershipVersion", ge=1)
    authorising_grant_id: UUID = Field(alias="authorisingGrantId")
    expected_grant_version: int = Field(alias="expectedGrantVersion", ge=1)
    dispositions: tuple[DependantDispositionPayload, ...] = Field(max_length=128)


class PredecessorCancellationPreviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    preview_hash: str = Field(serialization_alias="previewHash")
    package_id: UUID = Field(serialization_alias="packageId")
    package_version: int = Field(serialization_alias="packageVersion")
    dependant_count: int = Field(serialization_alias="dependantCount")
    planned_package_version: int = Field(serialization_alias="plannedPackageVersion")


class CancelPredecessorCommandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    command_id: UUID = Field(alias="commandId")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=128)
    request: PredecessorCancellationPayload
    preview_hash: str = Field(alias="previewHash", pattern=r"^[0-9a-f]{64}$")


class PredecessorCancellationResultResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    package_id: UUID = Field(serialization_alias="packageId")
    package_version: int = Field(serialization_alias="packageVersion")
    cancelled_dependants: int = Field(serialization_alias="cancelledDependants")
    unlinked_dependants: int = Field(serialization_alias="unlinkedDependants")
    replaced_dependants: int = Field(serialization_alias="replacedDependants")
    replayed: bool
