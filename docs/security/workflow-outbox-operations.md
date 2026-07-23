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

Monitor pending age, attempts, expired claims and dead-letter count. Every poll
consumes the dispatch result and emits bounded structured totals for claimed,
delivered, failed and newly dead-lettered work. Logs and metrics identify event
counts and oldest pending age, but never event payloads, credentials or exception
bodies that could contain customer data. A non-zero dead-letter count is an
alertable operational failure, not a silently exhausted retry.

`/api/v1/metrics` reads only the dispatcher's cached outbox snapshot, so a scrape
cannot trigger an outbox-table aggregate or compete with delivery for a database
connection. Local and test environments may scrape without credentials. Hosted
environments fail startup without a random `COEUS_METRICS_BEARER_TOKEN` of at
least 32 characters and require it as an `Authorization: Bearer` credential.
Keep the route on private monitoring ingress as an additional network boundary;
never put the token in a URL or log it.

A dead letter requires investigation of the handler and destination before
replay. The read-only operator view deliberately exposes aggregate pending,
retrying and dead-letter counts plus oldest pending age. Event-level details and
payloads are not exposed through the application API.

Alert when a configured dispatcher reports `coeus_outbox_available 0`, any
`coeus_outbox_dead_letter_messages`, or a sustained increase in
`coeus_outbox_oldest_pending_age_seconds`. A retrying count is an investigation
signal; correlate it with bounded dispatcher logs before deciding to replay.

Replay is an RBAC-protected operator action requiring an explicit reason. It is
audited and idempotent. Delivered work returns `already_delivered`; pending or
actively claimed work returns `already_pending`. A successful dead-letter replay
clears `dead_lettered_at`, resets `available_at`, clears the bounded last error
and retains the same `event_id`; it never inserts a replacement event. The handler
and destination still use that event ID as their idempotency key.

Before enabling hosted state-changing automation, exercise retry exhaustion,
dead-letter alerting and replay against an idempotent handler. The drill proves
that a repeat replay cannot duplicate the side effect and that logs, metrics and
the operator view expose no payload data.

Database restore and object-storage restore must use the same recovery point.
After restore, compare ticket versions and outbox uniqueness before resuming
writers or dispatchers. Quiesce dispatchers before rollback or reverse
projection so no side effect is delivered from an unverified state.

The [coordinated backup and restore drill](../runbooks/coordinated-backup-restore.md)
supplies application-level evidence for exact manifests, claim reset,
canonical ticket validation and audience reconciliation. Production physical
or managed-backup evidence remains a separate staging gate.

## Relational code rollback

Stop API and worker ticket writers, then run:

```powershell
uv run --directory apps/api python -m coeus.tools.reverse_ticket_projection --confirm-quiesced
```

The command verifies every relational aggregate hash and replaces the legacy
ticket namespace and records its relational baseline in one database
transaction. It refuses to run without the explicit quiescence acknowledgement.
After it completes, start the rollback candidate in legacy read mode, validate
ticket counts and sample current states, then resume traffic. A reconciliation
failure leaves the prior legacy namespace unchanged and must not be bypassed.

Before returning from N-1, quiesce its writers and reconcile any legacy-only
writes into the relational authority:

```powershell
uv run --directory apps/api python -m coeus.tools.reconcile_legacy_tickets `
  --confirm-quiesced --operator "change-operator" `
  --reason "Return from approved N-1 compatibility window"
```

The operation refuses stale relational baselines, malformed legacy aggregates
and replay, then commits the relational replacement, counter, validation and
audit evidence atomically. The complete stop, validation and restart sequence
is in the [ticket rollback and reconciliation runbook](../runbooks/ticket-code-rollback-reconciliation.md).

Alembic revision `20260713_0012` converts migration-era legacy payloads to stable
codec identities and recomputes the runtime SHA-256 canonical digest. The real
PostgreSQL migration harness proves legacy upgrade, relational validation,
compare-and-swap mutation and reverse projection as one compatibility chain.
The forward-reconciliation PostgreSQL suite additionally proves that N-1-only
writes become current relational state, a concurrent relational write fails
closed, corrupt legacy input is rejected and a completed checkpoint cannot be
replayed.
Relational startup also validates every aggregate ID, canonical hash, requester,
lifecycle state and capacity flag before making the store available. A mismatch
is a cutover failure and must be reconciled rather than bypassed.
