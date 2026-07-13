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

The hosted QC release handler uses the durable event identifier for both the
in-app notification and recorded email. Replaying the same event therefore
returns the existing records instead of creating duplicates. Missing, inactive
or malformed requester payloads fail delivery and enter the bounded retry and
dead-letter path.

## Current transaction boundary

In PostgreSQL relational mode, QC approval commits the version-checked ticket,
published Store projection, dissemination and feedback records carried by the
ticket, audit event and release-notification intent through
`WorkflowTransactionPort`. The transaction locks the expected ticket row before
writing and returns the existing `409 ticket_changed` contract to a stale
competitor. Object bytes are ingested before this short database transaction
and are discarded if the transaction fails. Provider calls and notification
delivery remain outside it.

Requester cancellation, no-match consent, collect choice and delivery
confirmation use the same version-locked ticket and audit transaction. These
single-ticket transitions create the ordinary `ticket_shadow_changed` event but
do not create an external notification intent.

Ticket creation uses a separate create-and-audit operation. A transaction-level
advisory lock protects the generated ticket identity before the insert, and an
existing identity fails with `409` instead of becoming an upsert. Intake edits,
attachments, submission, clarification, RFI outcomes, route decisions,
collaborators, assignment, analyst work, manager review, QC rejection and
feedback now use the single-ticket update operation.

Memory, file and non-relational modes retain a characterised compatibility
boundary. Multi-event audit batches commit as one store operation, and paired
ticket writes execute under one repository lock with rollback on confirmation
failure. They remain single-process development modes. Hosted symmetric links
lock both aggregates in ticket-ID order and commit both links plus audit evidence
together. Audited operations reject empty evidence groups. Cache refresh failure
after a durable commit is logged for operations, rather than being hidden.

Release notification insertion verifies the stored deterministic event ID and
payload after a uniqueness conflict. Different content for the same aggregate,
version and event type fails the database transaction closed. Remaining
adapter-contract and coordinated restore evidence is release-blocking.

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

Alembic revision `20260713_0012` converts migration-era legacy payloads to stable
codec identities and recomputes the runtime SHA-256 canonical digest. The real
PostgreSQL migration harness proves legacy upgrade, relational validation,
compare-and-swap mutation and reverse projection as one compatibility chain.
