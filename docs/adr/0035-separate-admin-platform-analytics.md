# ADR 0035: Separate Admin Platform Analytics

## Status

Accepted.

## Context

The original `/analytics/admin` route reused the global intelligence workflow
dashboard. It returned ticket-derived workload, product reuse rows, product
references and generated workflow trends. Those signals are useful to RFA and
Collection managers, but they are the wrong boundary for platform
administration and expose more operational detail than an administrator needs.

Administrators need account estate, access queue, AI service, search, voice,
security and platform health information. Existing services can provide safe
current-state aggregates and retained audit counts, but Coeus does not yet
persist authoritative token, cost, latency or embedding-call telemetry.

## Decision

- Keep `/analytics/rfa` and `/analytics/collection` on the existing authorised
  workflow, feedback and product-reuse contract.
- Add `/analytics/admin/platform` with a distinct aggregate-only platform
  response protected by `analytics:view_global`.
- Keep deprecated `/analytics/admin` for contract compatibility, but return
  only zero metrics and empty reuse/trend collections so it can no longer
  disclose intelligence workflow detail.
- Aggregate current account, pending registration, role, AI model, search
  index and voice configuration state on the server.
- Reduce retained audit events to 30-day counts for sign-ins, security events,
  configuration changes, assistant chat turns, RFI search runs and successful
  voice session starts. Return no event metadata or actor identifiers.
- Expose the audit coverage start and retention-limit state so bounded history
  is not presented as complete history.
- Label provider admission counters as process-lifetime health signals. Do not
  infer provider calls, token consumption, cost, latency or embedding API usage
  from chat turns or admission data.
- Prevent the admin schema from containing ticket, product, query, title,
  reference, username, actor ID or raw metadata fields.

## Consequences

The admin dashboard now answers platform administration questions without
showing intelligence workflow or product detail. RFA and Collection users keep
the operational views they need. The frontend and OpenAPI client use separate
admin and team response types, avoiding accidental rendering of operational
fields on the admin route.

Recent activity remains limited by the configured audit retention boundary,
and process counters reset with the API process. A future durable,
low-cardinality provider usage projection is required before Coeus can offer
accurate provider outcome, token, cost, latency or embedding-call analytics.
