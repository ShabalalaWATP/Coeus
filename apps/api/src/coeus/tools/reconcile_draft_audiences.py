"""Inspect or reconcile relational draft-product audiences."""

import argparse
import json
import sys

from coeus.core.config import Settings
from coeus.persistence.draft_audience_reconciliation import reconcile_draft_audiences


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--operator")
    parser.add_argument("--reason")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and (not args.operator or not args.reason):
        parser.error("--apply requires --operator and --reason")
    settings = Settings()
    if settings.persistence_provider != "postgres":
        parser.error("PostgreSQL persistence is required")
    try:
        report = reconcile_draft_audiences(
            settings.database_url,
            apply=args.apply,
            operator=args.operator,
            reason=args.reason,
        )
    except (RuntimeError, ValueError) as exc:
        sys.stderr.write(f"Draft audience reconciliation refused: {exc}\n")
        return 1
    if args.json:
        sys.stdout.write(json.dumps(report.to_dict(), sort_keys=True) + "\n")
    else:
        sys.stdout.write(
            f"Expected: {report.expected_count}; actual: {report.actual_count}; "
            f"missing: {len(report.missing)}; extra: {len(report.extra)}; "
            f"changed: {report.changed_count}.\n"
        )
    return 1 if report.missing or report.extra else 0


if __name__ == "__main__":
    raise SystemExit(main())
