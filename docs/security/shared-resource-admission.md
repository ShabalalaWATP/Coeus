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
scrape `/api/v1/metrics`, which emits OpenMetrics-compatible counters without
actor labels. Keep that route reachable only from the monitoring network at
hosted ingress.

## Lease lifecycle

PostgreSQL resource and provider reservations receive an opaque lease
identifier. Long-running work can renew an active lease. Renewal is fenced by
both lease identity and expiry, so an expired lease cannot be revived after
another worker has acquired freed capacity. Context exit releases an active
lease and remains safe after expiry. Ticket-creation reservations are short and
bounded by the provider timeout, then released as soon as the aggregate commit
finishes.

Remote embedding cache misses use the same provider reservation ledger as chat
calls. The caller's principal is required before provider acquisition, a
successful response commits one call, and provider failure refunds it. Cache
hits make no remote call. Mock and local embeddings remain offline and do not
consume an operator-funded provider reservation.

Crash recovery relies on lease expiry. Operators must set lease duration above
the normal p99 operation time and renew before expiry. A rising
`renewal_failed` counter indicates an overloaded worker, database delay or an
incorrect lease duration and should page the service owner.

## Ticket capacity diagnosis and recovery

`ticket_capacity_exhausted` can mean the retained-ticket limit is working as
configured, an expired creation lease remains visible, or a derived relational
column has drifted from a valid ticket payload. Use the dry-run-first [Ticket
Capacity Recovery](../runbooks/ticket-capacity-recovery.md) procedure to tell
these cases apart. It serialises repairs with live ticket admission, scopes
lease deletion to ticket creation, derives projections only from validated
canonical payloads and records every effective mutation atomically. It never
deletes an aggregate or overrides its workflow state. Normal process crashes
remain self-healing through automatic lease expiry.

## Provider circuit breaker

Remote LLM failures also feed a process-local circuit breaker. After
`COEUS_PROVIDER_CIRCUIT_FAILURE_THRESHOLD` consecutive failures, calls fall
back to the deterministic local provider without acquiring the remote service.
After `COEUS_PROVIDER_CIRCUIT_COOLDOWN_SECONDS`, one recovery probe is allowed;
other callers continue to fall back until that probe succeeds. Metrics expose
opens, rejections, probes, failures and successes without provider keys or
principal identifiers.
