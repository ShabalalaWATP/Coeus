"""Work-update delivery and personal notification preference writes."""

from uuid import uuid4

import pytest
from test_workspace_productivity_refusals_postgres import _command, _seed_ownership, _setup

from coeus.domain.workspace_productivity import WorkspaceRecordConflict
from coeus.persistence.workspace_productivity_postgres import PostgresWorkspaceProductivityStore

pytestmark = pytest.mark.postgres


def test_delivery_preferences_track_their_own_version(postgres_database_url: str) -> None:
    engine, actor, _, _ = _setup(postgres_database_url)
    store = PostgresWorkspaceProductivityStore(engine)

    def payload(**overrides: object) -> dict[str, object]:
        return {"mode": "digest", "due_reminders": True, "expected_version": 0, **overrides}

    with pytest.raises(ValueError, match="due reminders setting is invalid"):
        store.save_preferences(_command(actor, "save_preferences", payload(due_reminders="yes")))
    with pytest.raises(ValueError):
        store.save_preferences(_command(actor, "save_preferences", payload(mode="carrier-pigeon")))
    with pytest.raises(WorkspaceRecordConflict, match="delivery preferences version changed"):
        store.save_preferences(_command(actor, "save_preferences", payload(expected_version=5)))

    created = store.save_preferences(_command(actor, "save_preferences", payload()))
    assert created.version == 1 and created.due_reminders

    updated = store.save_preferences(
        _command(
            actor,
            "save_preferences",
            payload(expected_version=1, mode="immediate", due_reminders=False),
        )
    )
    assert updated.version == 2 and not updated.due_reminders
    assert store.get_preferences(actor) == updated
    engine.dispose()


def test_a_work_update_event_key_is_validated_and_never_reused(
    postgres_database_url: str,
) -> None:
    engine, actor, root_id, grants = _setup(postgres_database_url)
    store = PostgresWorkspaceProductivityStore(engine)
    ticket_id, other_ticket = uuid4(), uuid4()
    _seed_ownership(engine, actor, root_id, ticket_id)
    _seed_ownership(engine, actor, root_id, other_ticket)

    def payload(**overrides: object) -> dict[str, object]:
        return {
            "update_id": uuid4(),
            "recipient_user_id": actor,
            "event_key": "ticket-assigned:1",
            "kind": "assignment",
            "unit_id": root_id,
            "object_type": "ticket",
            "object_id": ticket_id,
            "authorising_grant_id": grants["workspace:configure"],
            "expected_grant_version": 1,
            **overrides,
        }

    for invalid in ("", " padded ", "x" * 129):
        with pytest.raises(ValueError, match="event key is invalid"):
            store.deliver_update(_command(actor, "deliver_update", payload(event_key=invalid)))

    delivered = store.deliver_update(_command(actor, "deliver_update", payload()))
    repeated = store.deliver_update(_command(actor, "deliver_update", payload()))
    assert delivered.update_id == repeated.update_id

    # The same event key must not be re-pointed at another record.
    with pytest.raises(WorkspaceRecordConflict, match="event key was reused"):
        store.deliver_update(_command(actor, "deliver_update", payload(object_id=other_ticket)))
    engine.dispose()
