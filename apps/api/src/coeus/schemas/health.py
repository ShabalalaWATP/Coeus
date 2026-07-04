from typing import Literal

from pydantic import BaseModel, ConfigDict

HealthStatus = Literal["ok", "ready", "not_ready"]


class ComponentStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    status: Literal["ready", "not_ready"]
    detail: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: HealthStatus
    service: str
    environment: str
    request_id: str


class ReadinessResponse(HealthResponse):
    components: list[ComponentStatus]
