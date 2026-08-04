"""Strict, privacy-minimised contracts for trusted work-update events."""

from dataclasses import dataclass
from uuid import UUID

from coeus.domain.workspace_productivity import WorkUpdateKind

WORK_UPDATE_REQUESTED = "workspace_work_update_requested"
_FIELDS = {
    "schema_version",
    "recipient_user_id",
    "kind",
    "unit_id",
    "object_type",
    "object_id",
}
_OBJECT_TYPES = {"ticket", "work_package", "calendar", "grant"}


@dataclass(frozen=True)
class WorkUpdateEvent:
    recipient_user_id: UUID
    kind: WorkUpdateKind
    unit_id: UUID
    object_type: str
    object_id: UUID

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "recipient_user_id": str(self.recipient_user_id),
            "kind": self.kind.value,
            "unit_id": str(self.unit_id),
            "object_type": self.object_type,
            "object_id": str(self.object_id),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "WorkUpdateEvent":
        if set(payload) != _FIELDS or payload.get("schema_version") != 1:
            raise ValueError("work-update payload contract is invalid")
        object_type = payload.get("object_type")
        if not isinstance(object_type, str) or object_type not in _OBJECT_TYPES:
            raise ValueError("work-update object type is invalid")
        try:
            return cls(
                UUID(str(payload["recipient_user_id"])),
                WorkUpdateKind(str(payload["kind"])),
                UUID(str(payload["unit_id"])),
                object_type,
                UUID(str(payload["object_id"])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("work-update payload values are invalid") from exc
