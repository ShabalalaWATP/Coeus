"""Staff-only API projections for bounded advisory-agent output."""

from pydantic import BaseModel, ConfigDict, Field


class AgentAdviceItemResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    code: str
    detail: str
    references: list[str]


class AgentAdviceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent: str
    outcome: str
    verdict: str | None
    shadow_only: bool = Field(serialization_alias="shadowOnly")
    context_references: list[str] = Field(serialization_alias="contextReferences")
    items: list[AgentAdviceItemResponse]
    provider_attempted: bool = Field(serialization_alias="providerAttempted")
