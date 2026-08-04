"""Inspect Sprint 24 organisation projections and capacity reservations."""

import argparse
import json
import sys
from uuid import UUID

from coeus.core.config import Settings
from coeus.persistence.organisation_capacity_repair import (
    RepairAction,
    inspect_or_repair_organisation_capacity,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-reservations", action="store_true")
    parser.add_argument("--operator", type=UUID)
    parser.add_argument("--reason")
    parser.add_argument("--confirm-reviewed", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    action: RepairAction = "repair-reservations" if args.repair_reservations else "inspect"
    if action != "inspect" and (not args.operator or not args.reason or not args.confirm_reviewed):
        parser.error("repair requires --operator, --reason and --confirm-reviewed")
    settings = Settings()
    if settings.persistence_provider != "postgres":
        parser.error("PostgreSQL persistence is required")
    try:
        report = inspect_or_repair_organisation_capacity(
            settings.database_url,
            action=action,
            operator_user_id=args.operator,
            reason=args.reason,
            reviewed=args.confirm_reviewed,
        )
    except (RuntimeError, ValueError) as exc:
        sys.stderr.write(f"Sprint 24 repair refused: {exc}\n")
        return 1
    if args.json:
        sys.stdout.write(json.dumps(report.to_dict(), sort_keys=True) + "\n")
    else:
        sys.stdout.write(
            f"Topology issues: {len(report.topology_issues)}; ownership issues: "
            f"{len(report.ownership_issues)}; reservation issues: "
            f"{len(report.reservation_issues)}; truncated: {report.truncated}; "
            f"changed: {report.changed_count}.\n"
        )
    return 1 if report.has_issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
