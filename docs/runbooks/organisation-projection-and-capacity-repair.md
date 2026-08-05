# Organisation Projection And Capacity Repair

Use this runbook when Sprint 24 readiness or an operator observes organisation
closure, task-ownership or capacity-reservation drift. The default operation is
read-only. It returns bounded opaque record identifiers and issue codes only.
It does not print personal details, calendar events, calendar notes, ticket
content or the database URL.

This procedure does not activate organisation cutover, routing or JIOC
evaluation. It does not grant authority and is not a substitute for current
authorisation checks.

## Read-only inspection

Set `COEUS_DATABASE_URL` and `COEUS_PERSISTENCE_PROVIDER=postgres`, then run:

```powershell
uv run --directory apps/api python -m coeus.tools.organisation_capacity_repair `
  --json
```

Preserve the JSON output with the incident or change record. A non-zero exit
means drift remains or the 500-row bound was exceeded. The report separates:

- `topology_issues`: missing, unexpected or wrong-depth closure rows when
  compared with the canonical single-parent organisation tree;
- `ownership_issues`: work-package/team-ownership disagreement, missing
  work-package ownership or ownership with no canonical ticket; and
- `reservation_issues`: a reservation/package identity mismatch, an elapsed
  hold or a live reservation attached to a terminal package.

The tool takes a transaction-scoped advisory lock so its three inspections
share one operator boundary. API writers may continue to run, but a repair
review should use a quiet maintenance window so the evidence remains easy to
interpret.

## Mandatory manual escalation

Do not edit `organisation_unit_closure` or `team_task_ownership` directly.
Those projections participate in management and ticket visibility. Restoring a
row can broaden authority. The current relational evidence cannot distinguish
every authorised historical correction from corruption, so this tool provides
no topology or task-ownership mutation.

Escalate any of these conditions to the service owner and security reviewer:

- any topology or ownership issue;
- `reservation_package_mismatch`;
- a truncated report;
- an invalid UUID or constraint failure; or
- drift that returns after a successful reservation repair.

Quiesce affected workflow writers, preserve the report, inspect immutable
work-package history and audit/outbox evidence, and choose either a normal
authorised workflow command or recovery from a known coherent backup. Never
infer ownership from a team name, role, display name or reporting label.

## Narrow reservation repair

Two states are uniquely derivable and may be repaired after human review:

- a `held` reservation whose persisted expiry is already elapsed becomes
  `expired`; and
- a `held` or `active` reservation whose canonical package is `complete` or
  `cancelled` becomes `released`.

The repair rechecks reservation/package ticket, workflow-leg and accountable
owner identities in the update transaction. It refuses all reservation repair
when a non-repairable mismatch is present. It never deletes a reservation,
changes reserved minutes, moves a person or package, edits ticket state, reads
calendar note content or creates a replacement reservation.

After reviewing every reservation ID in the inspection evidence, run:

```powershell
uv run --directory apps/api python -m coeus.tools.organisation_capacity_repair `
  --repair-reservations `
  --operator "00000000-0000-0000-0000-000000000000" `
  --reason "Reviewed elapsed holds and terminal package reservations" `
  --confirm-reviewed `
  --json
```

`--operator` is the authenticated operator's stable user UUID, not a name or
role. The bounded reason, changed reservation IDs and count are written to the
`capacity_reservation_drift_repaired` audit event and outbox record in the same
transaction as the state changes. An empty repair is idempotent and emits no
event.

## Verification

Re-run the read-only command. Success requires zero issues and
`truncated=false`. Confirm the audit and outbox records share the repair event
type, preserve both reports, then resume any paused workflow writers.

If only topology or ownership issues remain, the reservation repair has done
all that this runbook permits. Keep Sprint 24 cutover gated and follow the
manual escalation path above.

## Migration 0036 rollback boundary

Migration 0036 scopes capacity reservation idempotency keys by actor. After two
actors legitimately use the same key, the previous global unique constraint
cannot represent the stored evidence. The 0036 downgrade checks for that state
before changing any table or constraint and raises an actionable error. The
failed migration transaction leaves the Alembic revision, composite constraint,
handover schema and reservation rows unchanged.

Do not delete reservations, rewrite keys or merge actors to force a downgrade.
Preserve the database and migration error with the change record, keep services
on 0036 (or a later forward-compatible revision), and investigate the original
rollback reason. If rollback is mandatory, quiesce writers and restore a tested,
coherent backup taken before 0036. Verify its Alembic revision is 0035, confirm
the global key constraint, run the normal integrity and migration checks, then
resume services. If no suitable backup exists, recovery is forward-only and
requires a reviewed corrective migration rather than manual data mutation.
