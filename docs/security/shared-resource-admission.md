# Shared Resource Admission

Coeus reserves scarce upload, search, provider-call and retained-ticket
capacity before starting work. Hosted environments use atomic PostgreSQL
leases. Local and test environments use process-local reservations with the
same policy semantics.

## Enforcement modes

`COEUS_SHARED_RESOURCE_ADMISSION_MODE`, `COEUS_PROVIDER_ADMISSION_MODE` and
`COEUS_TICKET_ADMISSION_MODE` each have three explicit values:

- `observe`: admit work, record any limit that would have denied it, and use
  only during a measured rollout window.
- `deployment`: enforce shared concurrency and unit ceilings, while recording
  principal-limit pressure without denying it.
- `principal`: enforce both deployment and per-principal ceilings. This is the
  secure default in every environment.

Invalid or non-positive reservations are always rejected. Mode changes require
a normal configuration rollout and process restart. Roll back from `principal`
to `deployment` only for a diagnosed false-positive principal limit. Use
`observe` only with an owner, an end time and external capacity protection.

## Metrics and privacy

Controllers record low-cardinality counters by resource and outcome:
`admitted`, `observed_denial`, `denied_deployment`, `denied_principal`,
`denied_invalid`, `renewed` and `renewal_failed`. Principal identifiers are
deliberately excluded from metric labels. Hosted telemetry exporters should
scrape these counters through the application observability integration rather
than adding actor labels.

## Lease lifecycle

PostgreSQL resource and provider reservations receive an opaque lease
identifier. Long-running work can renew an active lease. Renewal is fenced by
both lease identity and expiry, so an expired lease cannot be revived after
another worker has acquired freed capacity. Context exit releases an active
lease and remains safe after expiry. Ticket-creation reservations are short and
bounded by the provider timeout, then released as soon as the aggregate commit
finishes.

Crash recovery relies on lease expiry. Operators must set lease duration above
the normal p99 operation time and renew before expiry. A rising
`renewal_failed` counter indicates an overloaded worker, database delay or an
incorrect lease duration and should page the service owner.
