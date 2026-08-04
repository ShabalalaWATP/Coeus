"""Command-line entry point for the explicit Sprint 24 performance gate."""

import argparse
import os
from pathlib import Path
from urllib.parse import urlsplit

from tests.performance.performance_runner import run_gate


def _database_url() -> str:
    value = os.getenv("COEUS_PERFORMANCE_DATABASE_URL", "")
    if not value:
        raise SystemExit("COEUS_PERFORMANCE_DATABASE_URL is required")
    parsed = urlsplit(value.replace("postgresql+psycopg://", "postgresql://", 1))
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1", "postgres"}:
        raise SystemExit("the performance gate only accepts a local or CI PostgreSQL host")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_gate(_database_url(), args.output)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
