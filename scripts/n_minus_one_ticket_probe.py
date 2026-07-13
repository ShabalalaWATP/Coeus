"""Run one ticket mutation through an N-1 Coeus source tree."""

import argparse
import json
import sys
from dataclasses import replace
from uuid import UUID

from coeus.domain.enums import TicketState
from coeus.persistence.state_store import PostgresStateStore
from coeus.repositories.tickets import InMemoryTicketRepository


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--ticket-id", required=True, type=UUID)
    args = parser.parse_args()

    repository = InMemoryTicketRepository(PostgresStateStore(args.database_url))
    ticket = repository.get(args.ticket_id)
    if ticket is None:
        raise RuntimeError("N-1 did not find the reverse-projected ticket.")
    updated = replace(
        ticket,
        state=TicketState.INFO_REQUIRED,
        intake=replace(ticket.intake, title="Updated by the N-1 compatibility probe"),
    )
    if not repository.save_if_current(ticket, updated):
        raise RuntimeError("N-1 ticket compare-and-swap unexpectedly conflicted.")
    restored = repository.get(args.ticket_id)
    if restored != updated:
        raise RuntimeError("N-1 could not read its committed ticket mutation.")
    sys.stdout.write(
        json.dumps(
            {
                "result": "updated",
                "state": restored.state.value,
                "ticket_id": str(restored.ticket_id),
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
