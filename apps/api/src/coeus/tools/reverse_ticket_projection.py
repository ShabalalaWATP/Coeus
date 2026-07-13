"""Reverse-project relational tickets after operators have quiesced writers."""

import argparse
import sys

from coeus.core.config import Settings
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.ticket_reverse_projection import reverse_project_ticket_state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-quiesced",
        action="store_true",
        help="confirm API and worker ticket writers are stopped",
    )
    args = parser.parse_args()
    if not args.confirm_quiesced:
        parser.error("--confirm-quiesced is required to protect rollback consistency")
    settings = Settings()
    if settings.persistence_provider != "postgres":
        parser.error("PostgreSQL persistence is required")
    # Ensure expanded schemas exist before entering the reverse-projection
    # transaction. This does not mutate a ticket aggregate.
    PostgresStateStore(settings.database_url, "relational").load_ticket_state()
    count = reverse_project_ticket_state(settings.database_url)
    sys.stdout.write(f"Reverse-projected {count} ticket aggregates into the legacy namespace.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
