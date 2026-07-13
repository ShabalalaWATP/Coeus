# ADR 0026: Versioned Workflow Transactions And Outbox

## Status

Accepted for Sprint 17, 2026-07-13.

First production adapter slice implemented for QC release on 2026-07-13. The
broader workflow cutover and restore gates remain in progress.

## Context

Whole-namespace ticket persistence makes mutation cost grow with retained data.
State checks also occur before separate ticket, product, audit and notification
writes. Deep scan `abf0e143` reproduced cancellation and QC release both
succeeding from one snapshot, leaving workflow and publication inconsistent.

## Decision

- A ticket is a versioned relational aggregate. Every transition uses a database
  version predicate or equivalent compare-and-swap at the commit boundary.
- `WorkflowTransactionPort` owns one SQLAlchemy connection and supplies
  transaction-scoped ticket, Store, audit and outbox views. Repositories do not
  open independent transactions for one unit of work.
- Release, product linkage, dissemination, feedback request, audit evidence and
  one uniquely keyed outbox intent commit in one short transaction.
- Lock ordering is deterministic and isolation is documented per transaction.
  A stale transition returns the existing conflict contract without compensation.
- Provider calls, notification delivery and object-byte transfer remain outside
  the database transaction. Bytes are staged and promoted idempotently; the
  outbox delivers after commit and supports replay.
- Memory and file adapters implement the same contract for local development,
  but PostgreSQL is the durable multi-process authority.
- Migration uses expand, backfill, shadow, cutover and later contraction with one
  authoritative writer. Rollback reverse-projects current data while writers are
  quiesced; a stale snapshot is never used as current state.

## Consequences

- Existing API shapes and successful workflow outcomes remain stable; a genuine
  stale competitor receives `409`.
- Manual compensating saves are removed only after their workflow uses the new
  transaction port.
- Backfill, reconciliation, N-1 code, database/object restore, process restart,
  race ordering and outbox replay become release gates.

## Implemented slice

- PostgreSQL relational QC release owns the ticket row lock and commits the
  ticket, Store projection, audit event and uniquely keyed notification intent
  on one SQLAlchemy connection.
- Requester cancellation, no-match consent, collect choice and delivery
  confirmation use the same port for atomic ticket and audit persistence.
- A failed audit append rolls the complete unit back. Concurrent commits from
  the same expected ticket snapshot yield one winner and one conflict.
- The hosted dispatcher validates the notification payload, resolves an active
  requester and deduplicates in-app and email records by durable event ID.
- Local and non-relational adapters retain existing behaviour. Remaining
  transition classes and coordinated restore evidence are not yet complete.
