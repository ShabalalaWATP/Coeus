import pytest

from coeus.services.audit import AuditLog


class ToggleStateStore:
    def __init__(self) -> None:
        self.fail_saves = False
        self.payloads: dict[str, dict[str, object]] = {}

    def load(self, namespace: str) -> dict[str, object] | None:
        return self.payloads.get(namespace)

    def save(self, namespace: str, payload: dict[str, object]) -> None:
        if self.fail_saves:
            raise RuntimeError("state store unavailable")
        self.payloads[namespace] = payload


def test_audit_record_rolls_back_when_persistence_fails() -> None:
    state_store = ToggleStateStore()
    audit_log = AuditLog(state_store=state_store)
    audit_log.record("before_failure")

    state_store.fail_saves = True
    with pytest.raises(RuntimeError, match="state store unavailable"):
        audit_log.record("should_not_remain")

    assert [event.event_type for event in audit_log.list_events()] == ["before_failure"]
