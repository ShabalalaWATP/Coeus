"""Inspect or safely recover PostgreSQL retained-ticket capacity."""

import argparse
import json
import sys
from uuid import UUID

from coeus.core.config import Settings
from coeus.persistence.ticket_capacity_recovery import RecoveryAction, recover_ticket_capacity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--remove-expired", action="store_true")
    actions.add_argument("--repair-projection", action="store_true")
    actions.add_argument("--release-lease", type=UUID)
    parser.add_argument("--operator")
    parser.add_argument("--reason")
    parser.add_argument("--confirm-api-drained", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    action: RecoveryAction = "inspect"
    if args.remove_expired:
        action = "remove-expired"
    elif args.repair_projection:
        action = "repair-projection"
    elif args.release_lease:
        action = "release-lease"
    if action != "inspect" and (not args.operator or not args.reason):
        parser.error("mutations require --operator and --reason")
    if action == "release-lease" and not args.confirm_api_drained:
        parser.error("--release-lease requires --confirm-api-drained")
    settings = Settings()
    if settings.persistence_provider != "postgres":
        parser.error("PostgreSQL persistence is required")
    try:
        report = recover_ticket_capacity(
            settings.database_url,
            action=action,
            operator=args.operator,
            reason=args.reason,
            lease_id=args.release_lease,
            api_drained=args.confirm_api_drained,
        )
    except (RuntimeError, ValueError) as exc:
        sys.stderr.write(f"Ticket-capacity recovery refused: {exc}\n")
        return 1
    if args.json:
        sys.stdout.write(json.dumps(report.to_dict(), sort_keys=True) + "\n")
    else:
        sys.stdout.write(
            f"Retained: {report.retained_count}; active leases: "
            f"{len(report.active_lease_ids)}; expired leases: "
            f"{len(report.expired_lease_ids)}; projection issues: "
            f"{len(report.projection_issues)}; changed: {report.changed_count}.\n"
        )
    return 1 if report.projection_issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
