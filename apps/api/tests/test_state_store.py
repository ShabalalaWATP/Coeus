import json
from pathlib import Path

import pytest

from coeus.core.config import Settings
from coeus.persistence import state_store
from coeus.persistence.factory import build_state_store
from coeus.persistence.relational_schema import store_schema_statements
from coeus.persistence.state_store import (
    FileStateStore,
    MemoryStateStore,
    PostgresStateStore,
    _sync_database_url,
)


def test_memory_state_store_returns_isolated_snapshots() -> None:
    store = MemoryStateStore()
    payload = {"tickets": [{"id": "ticket-1"}]}
    store.save("tickets", payload)

    payload["tickets"].append({"id": "mutated-input"})
    loaded = store.load("tickets")
    assert loaded == {"tickets": [{"id": "ticket-1"}]}
    assert loaded is not None

    loaded["tickets"].append({"id": "mutated-output"})

    assert store.load("tickets") == {"tickets": [{"id": "ticket-1"}]}


def test_file_state_store_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{not-json", encoding="utf-8")
    store = FileStateStore(path)

    with pytest.raises(ValueError, match="not valid JSON"):
        store.load("tickets")


def test_file_state_store_requires_object_root(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("[]", encoding="utf-8")
    store = FileStateStore(path)

    with pytest.raises(ValueError, match="must contain a JSON object"):
        store.load("tickets")


def test_postgres_state_store_saves_and_loads_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine = FakeEngine()
    captured: dict[str, str] = {}

    def fake_create_engine(url: str, pool_pre_ping: bool) -> FakeEngine:
        captured["url"] = url
        captured["pool_pre_ping"] = str(pool_pre_ping)
        return fake_engine

    monkeypatch.setattr(state_store, "create_engine", fake_create_engine)
    store = PostgresStateStore("postgresql+asyncpg://coeus:coeus-local@localhost/coeus")

    store.save("tickets", {"count": 1})

    assert store.load("tickets") == {"count": 1}
    assert captured == {
        "url": "postgresql+psycopg://coeus:coeus-local@localhost/coeus",
        "pool_pre_ping": "True",
    }
    executed_sql = "\n".join(fake_engine.statements)
    assert "intelligence_store_products" in executed_sql
    assert "intelligence_store_assets" in executed_sql
    assert "intelligence_store_product_acgs" in executed_sql
    assert "intelligence_store_semantic_labels" in executed_sql
    assert "embedding vector(384)" in executed_sql
    assert "vector_cosine_ops" in executed_sql


def test_store_relational_schema_has_access_and_search_indexes() -> None:
    statements = "\n".join(store_schema_statements())

    assert "CREATE EXTENSION IF NOT EXISTS vector" in statements
    assert "search_document tsvector" in statements
    assert "USING gin(search_document)" in statements
    assert "USING gin(semantic_labels)" in statements
    assert "intelligence_store_product_acgs" in statements
    assert "idx_store_product_acgs_acg" in statements


def test_sync_database_url_leaves_non_asyncpg_urls() -> None:
    assert _sync_database_url("postgresql+psycopg://example") == "postgresql+psycopg://example"


def test_factory_builds_postgres_state_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(state_store, "create_engine", lambda *_args, **_kwargs: FakeEngine())

    store = build_state_store(
        Settings(
            environment="test",
            persistence_provider="postgres",
            database_url="postgresql+asyncpg://coeus:coeus-local@localhost/coeus",
        )
    )

    assert isinstance(store, PostgresStateStore)


class FakeEngine:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, object]] = {}
        self.statements: list[str] = []

    def begin(self) -> "FakeConnection":
        return FakeConnection(self)


class FakeConnection:
    def __init__(self, engine: FakeEngine) -> None:
        self._engine = engine

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        return None

    def execute(self, statement: object, params: dict[str, object] | None = None) -> "FakeResult":
        sql = str(statement).strip()
        self._engine.statements.append(sql)
        if sql.startswith("SELECT") and params is not None:
            return FakeResult(self._engine.rows.get(str(params["namespace"])))
        if sql.startswith("INSERT") and params is not None:
            self._engine.rows[str(params["namespace"])] = json.loads(str(params["payload"]))
        return FakeResult(None)


class FakeResult:
    def __init__(self, payload: dict[str, object] | None) -> None:
        self._payload = payload

    def first(self) -> tuple[dict[str, object]] | None:
        return (self._payload,) if self._payload is not None else None
