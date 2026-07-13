# Ticket Capacity Recovery

Use this runbook when ticket creation returns `ticket_capacity_exhausted`, or
when relational startup reports a ticket-capacity projection mismatch. Full
capacity can be legitimate. Never delete tickets, rewrite workflow state or
raise a quota as an incident shortcut.

## Diagnose

Set `COEUS_DATABASE_URL` and `COEUS_PERSISTENCE_PROVIDER=postgres`, then run the
read-only default:

```powershell
uv run --directory apps/api python -m coeus.tools.ticket_capacity_recovery
```

Add `--json` for automation. Output contains only opaque principal and lease
identifiers, counts and projection status. It never prints the database URL,
ticket payloads or user names.

Interpret the result in this order:

1. A retained count at the configured limit is not corruption. Close or cancel
   tickets through authorised application workflows, or review a normal
   configuration rollout.
2. Expired `ticket_creation` leases are safe to remove. Normal admission also
   removes them automatically after a crashed creator.
3. A repairable projection issue means derived requester, state or capacity
   columns disagree with a valid, hash-matching ticket payload.
4. A non-repairable issue means payload type, aggregate identity or canonical
   hash cannot be trusted. Stop and investigate. The tool will not rewrite it.

## Remove expired creation leases

```powershell
uv run --directory apps/api python -m coeus.tools.ticket_capacity_recovery `
  --remove-expired --operator "incident-operator" `
  --reason "expired creation leases confirmed after process failure"
```

Only expired `ticket_creation` rows are deleted. Upload, search and provider
leases remain untouched. The mutation and audit event commit atomically under
the same PostgreSQL advisory lock used by ticket admission.

## Repair derived projection columns

```powershell
uv run --directory apps/api python -m coeus.tools.ticket_capacity_recovery `
  --repair-projection --operator "incident-operator" `
  --reason "derived projection drift confirmed"
```

The command derives values from the allow-listed ticket codec, validates the
canonical SHA-256 and aggregate identity, updates only the three derived
columns, then reconciles every relational ticket before commit. It does not
change the ticket payload, lifecycle, version or canonical hash.

## Break-glass release of one active lease

Stop every API and worker process first. Confirm that no ticket creator can
still commit, then release one reviewed opaque lease:

```powershell
uv run --directory apps/api python -m coeus.tools.ticket_capacity_recovery `
  --release-lease "00000000-0000-0000-0000-000000000000" `
  --confirm-api-drained --operator "incident-operator" `
  --reason "named abandoned lease confirmed after full drain"
```

The tool refuses unknown, expired or non-ticket leases and does not provide a
bulk active-lease operation. Releasing a live creator's lease could permit a
temporary quota overshoot, which is why the drained-system acknowledgement is
mandatory.

## Verification and evidence

Re-run the dry-run command after any repair. Preserve its JSON output with the
incident record and confirm the matching audit event:

- `ticket_capacity_expired_leases_recovered`
- `ticket_capacity_projection_repaired`
- `ticket_capacity_active_lease_force_released`

Database errors and audit failures roll back the entire operation. A repeated
safe cleanup is idempotent and produces no mutation event when nothing changed.
