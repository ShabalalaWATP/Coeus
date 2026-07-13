# Security Repair Baseline, 13 July 2026

## Scope

This is a synthetic, mock-provider baseline for Sprint 17. It is not a
production capacity claim. Reproduce it from the repository root with:

```powershell
uv run --project apps/api python scripts/measure_security_baselines.py
```

The run used Windows, Python 3.13.3 and the committed mock/local adapters. The
health sample contains 30 in-process ASGI requests. Upload figures contain five
10 MB streamed staging runs. Ticket mutation seeds the in-memory aggregate and
times one persistence write at 10 and 10,000 retained tickets.

## Recorded Baseline

| Measure | Result |
|---|---:|
| Health latency p50 | 1.671 ms |
| Health latency p95 | 2.287 ms |
| 10 MB staged upload p50 | 9.663 ms |
| 10 MB staged upload p95 | 9.995 ms |
| Upload peak Python heap | 2,129,684 bytes |
| Upload peak working-set delta | 1,085,440 bytes |
| Upload temporary storage | 10,000,000 bytes |
| Similarity corpus | 101 candidates |
| Maximum embedding calls | 33 |
| Ticket mutation, 10 retained tickets | 0.793 ms |
| Ticket mutation, 10,000 retained tickets | 1,353.085 ms |
| Ticket mutation ratio | 1,706.29 times |

## Interpretation

- Streamed staging keeps incremental Python and process memory substantially
  below the payload size while temporary storage grows exactly with accepted
  bytes.
- Similarity embedding work is fixed at one query plus 32 candidates.
- Whole-corpus ticket persistence scales unacceptably. The 10,000-ticket write
  is over 1,700 times the 10-ticket write, confirming that Phase 4 per-ticket
  relational persistence is release-blocking rather than optional cleanup.
- Migration 0008 expands into versioned per-ticket rows and a uniquely keyed
  outbox. After two successive 13-test PostgreSQL candidate validations,
  `relational` became the default. The mutation contract executes five SQL
  statements at both 10 and 10,000 rows; `shadow_validate` and `legacy` remain
  explicit rollback modes.
- Migration 0009 adds the indexed draft-audience projection. Hosted provider,
  upload, search and ticket admission now share PostgreSQL state across API
  processes; local/mock operation retains explicit process-local adapters.

Numbers vary with host load. Security gates compare behaviour and asymptotic
work, not exact millisecond equality.
