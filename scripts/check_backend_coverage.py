"""Fail when backend line or branch coverage is below the required threshold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def percentage(covered: int, total: int) -> float:
    return 100.0 if total == 0 else covered * 100.0 / total


def coverage_metrics(report: dict[str, Any]) -> tuple[float, float]:
    totals = report["totals"]
    return (
        percentage(int(totals["covered_lines"]), int(totals["num_statements"])),
        percentage(int(totals["covered_branches"]), int(totals["num_branches"])),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--minimum", type=float, default=95.0)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    line_coverage, branch_coverage = coverage_metrics(report)
    print(f"Backend line coverage: {line_coverage:.2f}%")
    print(f"Backend branch coverage: {branch_coverage:.2f}%")
    failed = [
        name
        for name, value in (("line", line_coverage), ("branch", branch_coverage))
        if value < args.minimum
    ]
    if failed:
        print(
            f"Backend {', '.join(failed)} coverage is below the "
            f"{args.minimum:.2f}% release gate."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
