# Ticket Code Rollback And Forward Reconciliation

## Status

Active for the Sprint 17 PostgreSQL relational-ticket compatibility window.
Last verified locally: 2026-07-13.

This procedure supports a temporary rollback to an N-1 application revision
that reads and writes the legacy `tickets` namespace. It does not downgrade the
database schema. Keep the expanded schema and do not run destructive Alembic
downgrades.

## Preconditions

- Confirm that the candidate database is PostgreSQL and has a current backup.
- Stop every API, worker, job and operator path that can mutate tickets.
- Stop outbox dispatchers so no notification is delivered from an unverified
  workflow state.
- Record the current application revision, database recovery point, operator
  identity and incident or change reference.
- Verify that no ticket writer remains connected before either projection.

## Reverse-project before starting N-1

With `COEUS_DATABASE_URL` pointing at the quiesced database, run:

```powershell
uv run --directory apps/api python -m coeus.tools.reverse_ticket_projection `
  --confirm-quiesced
```

The command verifies every relational aggregate's canonical SHA-256 digest,
writes the complete legacy namespace and records an immutable baseline hash map
in `ticket_rollback_checkpoint`, all in one database transaction. Failure leaves
the prior legacy namespace and checkpoint unchanged.

Start the approved N-1 application in its legacy persistence mode. Validate
ticket counts and representative current states before admitting traffic. Keep
the rollback window short and retain the expanded relational tables.

## Return to the current application

Quiesce every N-1 ticket writer and dispatcher again. From the current revision,
run:

```powershell
uv run --directory apps/api python -m coeus.tools.reconcile_legacy_tickets `
  --confirm-quiesced `
  --operator "change-operator" `
  --reason "Return from approved N-1 compatibility window"
```

Forward reconciliation locks the compatibility namespace and relational rows.
It refuses to proceed if:

- the reverse-projection checkpoint is absent or malformed;
- a legacy aggregate is malformed, duplicated or not a ticket;
- any relational aggregate changed after the reverse projection; or
- the operator or reason evidence is missing or exceeds its bound.

On success, the operation replaces relational ticket rows, refreshes the
counter, validates the resulting relational projection, records one
`legacy_ticket_state_reconciled` audit event and removes the checkpoint in the
same transaction. Preserve the JSON report and audit event with the release or
incident evidence.

## Validation before resuming traffic

1. Start the current application with PostgreSQL relational persistence.
2. Confirm readiness succeeds, which validates every aggregate ID, hash,
   requester, lifecycle state and capacity flag.
3. Compare ticket count and representative state/version data with the N-1
   pre-quiescence evidence.
4. Exercise one authorised compare-and-swap mutation and verify its audit event.
5. Resume API traffic, then resume outbox dispatchers.

Never delete the checkpoint manually, edit either representation by hand or
bypass a reconciliation refusal. A relational-change refusal means the
quiescence boundary was violated and requires investigation and recovery from a
known coherent recovery point.
