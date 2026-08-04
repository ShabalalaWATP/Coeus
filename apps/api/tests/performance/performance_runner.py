"""Measure, validate and serialise Sprint 24 PostgreSQL performance evidence."""

import json
import os
import platform
import shutil
import statistics
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns
from uuid import uuid4

import psycopg
from tests.performance import performance_queries
from tests.performance.performance_contract import (
    BENCHMARKS,
    REFERENCE_PROFILE,
    REPORT_SCHEMA_VERSION,
    FixtureScale,
    validate_report,
)
from tests.performance.performance_fixture import cardinalities, create_fixture

SAMPLES = 20


def _milliseconds(call: Callable[[], None]) -> float:
    started = perf_counter_ns()
    call()
    return (perf_counter_ns() - started) / 1_000_000


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * percentile + 0.999999) - 1))
    return ordered[index]


def _git_revision() -> str | None:
    executable = shutil.which("git")
    if executable is None:
        return None
    try:
        return subprocess.run(  # noqa: S603 - fixed git arguments, resolved executable
            [executable, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def run_gate(
    database_url: str, output: Path, scale: FixtureScale | None = None
) -> dict[str, object]:
    fixture_scale = scale or FixtureScale()
    fixture_scale.validate()
    schema = f"sprint24_perf_{uuid4().hex}"
    dsn = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    results: list[dict[str, object]] = []
    with psycopg.connect(dsn) as connection:
        try:
            create_fixture(connection, schema, fixture_scale)
            actual = cardinalities(connection, schema)
            if actual != fixture_scale.as_dict():
                raise RuntimeError(f"fixture cardinality mismatch: {actual!r}")
            postgres_version = str(connection.info.server_version)
            calls: tuple[Callable[[], None], ...] = (
                lambda: performance_queries.tree_roster(connection, schema),
                lambda: performance_queries.board(connection, schema),
                lambda: performance_queries.descendant_calendar_capacity(connection, schema),
                lambda: performance_queries.recommendation_preview(connection, schema),
                lambda: performance_queries.assignment_commit(connection, schema, len(results)),
            )
            for contract, call in zip(BENCHMARKS, calls, strict=True):
                connection.commit()
                first = _milliseconds(call)
                samples = [_milliseconds(call) for _ in range(SAMPLES)]
                p95 = _percentile(samples, 0.95)
                results.append(
                    {
                        "name": contract.name,
                        "budget_ms": contract.budget_ms,
                        "result_limit": contract.result_limit,
                        "first_execution_ms": round(first, 3),
                        "warm_samples": len(samples),
                        "warm_p50_ms": round(statistics.median(samples), 3),
                        "warm_p95_ms": round(p95, 3),
                        "warm_max_ms": round(max(samples), 3),
                        "passed": p95 <= contract.budget_ms,
                    }
                )
        finally:
            connection.rollback()
            connection.execute(
                psycopg.sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    psycopg.sql.Identifier(schema)
                )
            )
            connection.commit()
    report: dict[str, object] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "reference_profile": REFERENCE_PROFILE,
        "observed_at": datetime.now(UTC).isoformat(),
        "revision": _git_revision(),
        "fixture": fixture_scale.as_dict(),
        "machine": {
            "runner": os.getenv("RUNNER_NAME", "local"),
            "runner_image_os": os.getenv("ImageOS"),  # noqa: SIM112 - GitHub variable
            "runner_image_version": os.getenv("ImageVersion"),  # noqa: SIM112
            "os": platform.platform(),
            "architecture": platform.machine(),
            "logical_cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "postgres_server_version_num": postgres_version,
        },
        "cold_cache_observation": {
            "method": "first execution after fixture load and analyse",
            "controlled": False,
            "note": (
                "first_execution_ms is informational; the gate does not claim "
                "PostgreSQL or operating-system cache eviction"
            ),
        },
        "benchmarks": results,
        "passed": all(bool(result["passed"]) for result in results),
    }
    validate_report(report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
