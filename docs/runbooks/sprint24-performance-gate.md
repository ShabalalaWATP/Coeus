# Sprint 24 Performance Gate

This explicit gate proves that the hierarchical workforce paths stay within
their approved warm-database p95 budgets at the minimum production-like scale.
It is scheduled weekly and can also be started manually in GitHub Actions. It
does not run in routine pull-request CI because it provisions 71,000 relational
records and collects repeated timing samples.

## Reference contract

The versioned reference profile is
`github-actions-ubuntu-24.04-postgresql-16-v1`. The gate creates a uniquely
named disposable PostgreSQL schema, loads exactly:

- 1,000 organisation units;
- 10,000 memberships;
- 50,000 calendar events;
- 10,000 active board cards; and
- a bounded 500-person recommendation cohort.

The assignment workload evaluates all 500 bounded candidates and ranks them,
while the operational preview deliberately returns only the top 10 people for
human review. The 501st row is a fail-closed sentinel. This keeps the scale gate
honest without widening the manager-facing response or override surface.

It applies the following budgets without tolerance or automatic adjustment:

| Workload | Warm p95 budget |
| --- | ---: |
| 100-row authorised tree and roster | 300 ms |
| 100-card authorised board page | 500 ms |
| 31-day authorised descendant calendar and capacity view | 750 ms |
| 500-candidate assignment preview | 1,000 ms |
| Assignment commit, excluding bounded retry | 1,000 ms |

Each path receives one first-execution observation and 20 warm samples. The
first observation is useful cold-start evidence, but it is not described as a
controlled cold-cache result because the runner does not evict PostgreSQL or
operating-system caches. This distinction prevents misleading comparisons.

## Run locally

Use a disposable local PostgreSQL database. The runner rejects non-local hosts.

```powershell
$env:COEUS_PERFORMANCE_DATABASE_URL = `
  'postgresql+psycopg://coeus:coeus-local@127.0.0.1:5432/coeus'
uv run --directory apps/api python -m tests.performance.run_performance_gate `
  --output ../../output/performance/sprint24-performance.json
```

The schema is dropped even when a benchmark fails. The JSON evidence records
the report schema, Git revision, runner and machine details, PostgreSQL version,
verified fixture cardinalities, first-execution observations, warm p50, warm
p95, maximum, approved budget and pass state for each path.

## Interpret and retain evidence

The command exits non-zero if any p95 exceeds its budget or if the evidence
contract is incomplete. GitHub uploads the JSON report even after failure.
Compare only runs with the same `reference_profile`; changing the runner image,
PostgreSQL major version, fixture, sample count or query contract requires a new
profile version and an architecture review. Never increase a budget merely to
make a run pass.

For a regression, retain the failing report, inspect query plans and database
statistics, then fix the query or index and rerun the same profile. Treat local
results as diagnostic evidence, not as a replacement for the reference gate.
