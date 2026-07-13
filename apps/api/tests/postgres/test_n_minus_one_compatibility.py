import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.ticket_forward_reconciliation import reconcile_legacy_ticket_state
from coeus.persistence.ticket_reverse_projection import reverse_project_ticket_state
from coeus.repositories.tickets import InMemoryTicketRepository

pytestmark = pytest.mark.postgres


def test_real_n_minus_one_writes_survive_forward_reconciliation(
    postgres_database_url: str,
) -> None:
    old_source = os.getenv("COEUS_N_MINUS_ONE_SOURCE")
    if not old_source:
        pytest.skip("COEUS_N_MINUS_ONE_SOURCE is not configured")
    old_source_path = Path(old_source).resolve()
    if not (old_source_path / "apps" / "api" / "src" / "coeus").is_dir():
        pytest.fail("COEUS_N_MINUS_ONE_SOURCE is not a Coeus source tree")

    relational = InMemoryTicketRepository(PostgresStateStore(postgres_database_url, "relational"))
    original = TicketRecord(
        ticket_id=uuid4(),
        reference=relational.next_reference(),
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title="Current release candidate"),
    )
    relational.save(original)
    assert reverse_project_ticket_state(postgres_database_url) == 1

    root = Path(__file__).resolve().parents[4]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(old_source_path / "apps" / "api" / "src")
    completed = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(root / "scripts" / "n_minus_one_ticket_probe.py"),
            "--database-url",
            postgres_database_url,
            "--ticket-id",
            str(original.ticket_id),
        ],
        cwd=old_source_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    probe = json.loads(completed.stdout)
    assert probe == {
        "result": "updated",
        "state": TicketState.INFO_REQUIRED.value,
        "ticket_id": str(original.ticket_id),
    }

    report = reconcile_legacy_ticket_state(
        postgres_database_url,
        operator="compatibility-gate",
        reason="Actual N-1 source compatibility test",
    )
    assert report.ticket_count == 1
    current_repository = InMemoryTicketRepository(
        PostgresStateStore(postgres_database_url, "relational")
    )
    restored = current_repository.get(original.ticket_id)
    expected = replace(
        original,
        state=TicketState.INFO_REQUIRED,
        intake=replace(original.intake, title="Updated by the N-1 compatibility probe"),
    )
    assert restored == expected

    current_update = replace(restored, state=TicketState.CANCELLED)
    assert current_repository.save_if_current(restored, current_update)
    assert current_repository.get(original.ticket_id) == current_update
