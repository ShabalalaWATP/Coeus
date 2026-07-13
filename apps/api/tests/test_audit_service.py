from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy.engine import Engine

from coeus.persistence.audit_store import (
    FileAuditEventStore,
    MemoryAuditEventStore,
    PostgresAuditEventStore,
)
from coeus.services.audit import AuditLog, _event_from_payload


class ToggleAuditStore(MemoryAuditEventStore):
    def __init__(self) -> None:
        super().__init__()
        self.fail_appends = False

    def append(self, event: dict[str, object]) -> None:
        if self.fail_appends:
            raise RuntimeError("audit store unavailable")
        super().append(event)


def test_audit_record_does_not_change_cache_when_append_fails() -> None:
    store = ToggleAuditStore()
    audit_log = AuditLog(event_store=store)
    audit_log.record("before_failure")

    store.fail_appends = True
    with pytest.raises(RuntimeError, match="audit store unavailable"):
        audit_log.record("should_not_remain")

    assert [event.event_type for event in audit_log.list_events()] == ["before_failure"]


def test_recent_cache_rollover_never_deletes_authoritative_history() -> None:
    store = MemoryAuditEventStore()
    audit_log = AuditLog(max_events=2, event_store=store)
    audit_log.record("user_credential_reset")
    for index in range(4):
        audit_log.record(f"public_failure_{index}")

    assert [event.event_type for event in audit_log.list_events()] == [
        "public_failure_2",
        "public_failure_3",
    ]
    assert [event.event_type for event in audit_log.list_page(10).events] == [
        "user_credential_reset",
        "public_failure_0",
        "public_failure_1",
        "public_failure_2",
        "public_failure_3",
    ]
    restored = AuditLog(max_events=2, event_store=store)
    assert [event.event_type for event in restored.list_events()] == [
        "public_failure_2",
        "public_failure_3",
    ]
    assert restored.list_page(10).events[0].event_type == "user_credential_reset"


def test_audit_batch_updates_store_and_cache_as_one_group() -> None:
    store = MemoryAuditEventStore()
    audit_log = AuditLog(event_store=store)

    recorded = audit_log.record_many(
        (("first", None, {"sequence": "1"}), ("second", "actor", {"sequence": "2"}))
    )

    assert [event.event_type for event in recorded] == ["first", "second"]
    assert [event.event_type for event in audit_log.list_events()] == ["first", "second"]
    with pytest.raises(ValueError, match="must not be empty"):
        audit_log.record_many(())


def test_audit_metadata_is_an_immutable_snapshot() -> None:
    metadata = {"decision": "allow"}
    event = AuditLog().record("decision_recorded", metadata=metadata)
    metadata["decision"] = "deny"

    assert dict(event.metadata) == {"decision": "allow"}
    with pytest.raises(TypeError):
        event.metadata["decision"] = "changed"  # type: ignore[index]


def test_concurrent_audit_records_remain_complete_with_a_bounded_cache() -> None:
    store = MemoryAuditEventStore()
    audit_log = AuditLog(max_events=10, event_store=store)

    with ThreadPoolExecutor(max_workers=8) as pool:
        tuple(pool.map(lambda index: audit_log.record(f"event_{index}"), range(50)))

    assert len(audit_log.list_events()) == 10
    assert len(audit_log.list_page(50).events) == 50


def test_file_audit_store_is_append_only_across_restart(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    first = AuditLog(max_events=1, event_store=FileAuditEventStore(path))
    first.record("privileged_change")
    first.record("public_failure")

    restored = AuditLog(max_events=1, event_store=FileAuditEventStore(path))

    assert [event.event_type for event in restored.list_events()] == ["public_failure"]
    assert [event.event_type for event in restored.list_page(10).events] == [
        "privileged_change",
        "public_failure",
    ]
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_file_audit_batch_survives_restart_as_one_group(tmp_path: Path) -> None:
    path = tmp_path / "audit-batch.jsonl"
    first = AuditLog(event_store=FileAuditEventStore(path))
    first.record_many((("first", None, {}), ("second", None, {})))

    restored = AuditLog(event_store=FileAuditEventStore(path))

    assert [event.event_type for event in restored.list_events()] == ["first", "second"]


def test_audit_input_bounds_and_payload_shapes_fail_closed() -> None:
    with pytest.raises(ValueError, match="max_events"):
        AuditLog(max_events=0)
    with pytest.raises(ValueError, match="page limit"):
        AuditLog().list_page(0)
    with pytest.raises(ValueError, match="payload must be an object"):
        _event_from_payload([])
    with pytest.raises(ValueError, match="metadata must be an object"):
        _event_from_payload(
            {
                "event_id": "event-1",
                "event_type": "test",
                "occurred_at": "2026-07-10T10:00:00+00:00",
                "actor_user_id": None,
                "metadata": [],
            }
        )


def test_file_audit_store_rejects_non_object_and_invalid_json_lines(tmp_path: Path) -> None:
    path = tmp_path / "invalid-audit.jsonl"
    path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain an object"):
        FileAuditEventStore(path).list_page(10)

    path.write_text("{invalid}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        FileAuditEventStore(path).list_page(10)


class FakeAuditResult:
    def mappings(self) -> FakeAuditResult:
        return self

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(())


class FakeAuditConnection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: object, _params: object = None) -> FakeAuditResult:
        self.statements.append(str(statement))
        return FakeAuditResult()


class FakeAuditTransaction:
    def __init__(self, connection: FakeAuditConnection) -> None:
        self.connection = connection

    def __enter__(self) -> FakeAuditConnection:
        return self.connection

    def __exit__(self, *_args: object) -> None:
        return None


class FakeAuditEngine:
    def __init__(self) -> None:
        self.connection = FakeAuditConnection()

    def begin(self) -> FakeAuditTransaction:
        return FakeAuditTransaction(self.connection)


def test_postgres_audit_store_initialises_schema_once() -> None:
    engine = FakeAuditEngine()
    store = PostgresAuditEventStore(cast(Engine, engine))
    event: dict[str, object] = {
        "event_id": "b7e7867e-1e46-401d-8cd5-80cf5b989092",
        "event_type": "test",
        "occurred_at": "2026-07-10T10:00:00+00:00",
        "actor_user_id": None,
        "metadata": {},
    }

    store.append(event)
    store.append(event)
    store.append_many((event, event))
    store.append_many(())

    assert sum("CREATE TABLE" in statement for statement in engine.connection.statements) == 1
