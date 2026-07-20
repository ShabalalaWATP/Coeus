from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CustomerProductDecisionRequest(BaseModel):
    meets_requirement: bool = Field(validation_alias="meetsRequirement")
    reason: str = Field(default="", max_length=2_000)
    unmet_criteria: list[str] = Field(
        default_factory=list, max_length=10, validation_alias="unmetCriteria"
    )

    @model_validator(mode="after")
    def require_rejection_reason(self) -> "CustomerProductDecisionRequest":
        if not self.meets_requirement and len(self.reason.strip()) < 3:
            raise ValueError("A reason is required when the product does not meet the requirement.")
        return self


class ManagerReanalysisDecisionRequest(BaseModel):
    decision: Literal["agree", "refer_to_jioc"]
    rationale: str = Field(min_length=3, max_length=2_000)


class JiocReanalysisDecisionRequest(BaseModel):
    decision: Literal["reanalyse", "close"]
    rationale: str = Field(min_length=3, max_length=2_000)
