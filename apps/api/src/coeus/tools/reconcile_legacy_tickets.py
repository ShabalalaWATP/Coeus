"""Reconcile quiesced N-1 ticket writes into relational persistence."""

import argparse
import json
import sys
from dataclasses import asdict

from coeus.core.config import Settings
from coeus.persistence.ticket_forward_reconciliation import reconcile_legacy_ticket_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-quiesced", action="store_true")
    parser.add_argument("--operator", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    if not args.confirm_quiesced:
        parser.error("--confirm-quiesced is required")
    settings = Settings()
    if settings.persistence_provider != "postgres":
        parser.error("PostgreSQL persistence is required")
    try:
        report = reconcile_legacy_ticket_state(
            settings.database_url,
            operator=args.operator,
            reason=args.reason,
        )
    except (RuntimeError, ValueError) as exc:
        sys.stderr.write(f"Legacy ticket reconciliation failed: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(asdict(report), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
