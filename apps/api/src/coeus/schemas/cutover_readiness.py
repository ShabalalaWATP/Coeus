"""Public-safe cutover-readiness HTTP contract."""

from pydantic import BaseModel, ConfigDict, Field

from coeus.domain.cutover_readiness import CutoverCheckCode, CutoverCheckStatus


class CutoverReadinessCheckResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: CutoverCheckCode
    status: CutoverCheckStatus
    observed_count: int = Field(serialization_alias="observedCount")
    required_count: int = Field(serialization_alias="requiredCount")


class CutoverReadinessResponse(BaseModel):
    ready: bool
    checks: list[CutoverReadinessCheckResponse]
