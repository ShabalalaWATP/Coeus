# ADR 0021: Shared Resource Budgets And Async Execution Boundaries

## Status

Accepted for Sprint 14B.

## Context

The sealed scan of revision `72a0dc58` found repeated cases where individually
valid requests created unbounded aggregate work, durable state, responses,
database connections or provider waits. Authentication and per-field limits do
not authorise unbounded consumption of shared service resources.

## Decision

- Every remotely reachable collection has an explicit count or aggregate byte
  budget at the service/domain boundary.
- List endpoints use cursor pagination and bounded summary DTOs. Mutation
  responses do not echo unbounded histories.
- File downloads stream bounded chunks and use per-user and global in-flight
  byte budgets.
- External provider calls use query-level call budgets, caching or batching,
  explicit timeouts and per-user/global concurrency controls.
- Blocking network or CPU work does not run on a FastAPI event-loop thread.
  Providers are async where practical; otherwise bounded offload is explicit.
- Offloaded work must not unconditionally commit a complete stale aggregate.
  Mutation application uses an expected-snapshot compare-and-swap, and audit
  rollback may restore only the exact snapshot written by that operation.
- Readiness checks use a fixed database budget through coalescing or a small
  shared semaphore and a dedicated timeout.
- Every limit has maximum, maximum-plus-one, legitimate-control and rollback
  tests. Rejection must not partially mutate durable state.

## Consequences

- Product requirements must choose concrete budgets rather than relying on
  host capacity or reverse proxies.
- Direct service callers and future transports receive the same enforcement as
  HTTP callers.
- Large legitimate histories use paging, summaries, retention or staged
  ingestion rather than one unlimited aggregate.
- Scaling remains local and single-writer. These controls do not activate the
  future GCP path or justify multiple API writers.
