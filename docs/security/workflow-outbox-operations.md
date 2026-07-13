# Workflow Outbox Operations

Coeus records workflow side-effect intents in `coeus_outbox` in the same
database transaction as the versioned ticket aggregate. Delivery occurs after
commit through `OutboxDispatcher` and `PostgresOutboxStore`.

## Claim and delivery rules

- Workers claim bounded batches with `FOR UPDATE SKIP LOCKED`.
- A claim has an opaque worker identifier and expiry time.
- Settlement requires the same worker identifier. Stale workers cannot mark a
  reclaimed message delivered or failed.
- Successful handlers mark the message delivered exactly once.
- Failed handlers clear the claim and schedule a bounded retry.
- At the configured attempt limit, the message is dead-lettered and excluded
  from normal claims.
- Handler errors are truncated before persistence. Secrets and payload content
  must never be included in exception messages.

Handlers must be idempotent because a process can complete an external side
effect and fail before marking the event delivered. The unique aggregate,
version and event-type key prevents duplicate intent creation, while the
external provider must use `event_id` as its idempotency key where supported.

## Operator checks

Monitor pending age, attempts, expired claims and dead-letter count. A dead
letter requires investigation of the handler and destination before replay.
Replay must clear `dead_lettered_at`, reset `available_at`, and retain the same
`event_id`; do not insert a replacement event.

Database restore and object-storage restore must use the same recovery point.
After restore, compare ticket versions and outbox uniqueness before resuming
writers or dispatchers. Quiesce dispatchers before rollback or reverse
projection so no side effect is delivered from an unverified state.

## Relational code rollback

Stop API and worker ticket writers, then run:

```powershell
uv run --directory apps/api python -m coeus.tools.reverse_ticket_projection --confirm-quiesced
```

The command verifies every relational aggregate hash and replaces the legacy
ticket namespace in one database transaction. It refuses to run without the
explicit quiescence acknowledgement. After it completes, start the rollback
candidate in legacy read mode, validate ticket counts and sample current states,
then resume traffic. A reconciliation failure leaves the prior legacy namespace
unchanged and must not be bypassed.
