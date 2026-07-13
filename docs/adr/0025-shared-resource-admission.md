# ADR 0025: Shared Principal And Deployment Resource Admission

## Status

Accepted for Sprint 17, 2026-07-13. This ADR supersedes the claim in ADR 0021
that endpoint-local budgets fully cover all reachable provider and collection
work; ADR 0021 remains useful tactical guidance.

## Context

Deep scan `abf0e143` found that chat, Store, similarity and RFI requests could
reset limits by changing endpoints, queries or ticket identities. Upload bytes
and authentication histories also lacked complete aggregate ownership. The
scarce resources are shared by a principal and deployment, not by one request.

## Decision

- Expensive work reserves semantic units before acquisition: provider calls or
  tokens, embedding calls, search slots, in-flight upload bytes, upload slots
  and retained tickets.
- Admission applies atomically to principal and deployment ceilings across
  application processes. PostgreSQL leases are the hosted authority.
- Every reservation has an identity, expiry, commit and resource-specific refund
  rule. A retry cannot commit or refund the same reservation twice.
- Provider gateways and bounded workers require reservation context. Ambient
  configured credentials do not grant unmetered execution.
- Anonymous receive bytes are controlled before multipart parsing by the ingress
  and ASGI receive boundary; the application governor cannot recover bytes that
  were already spooled.
- Failures are fail-closed for paid or shared resources. Mock/local providers
  use explicit finite development budgets, not an implicit bypass.
- Endpoint quotas, streaming, caches, single-flight work and bounded histories
  remain defence in depth through rollout and rollback.
- Metrics expose resource and saturation labels without principal identifiers.

## Consequences

- PostgreSQL admission becomes an availability dependency with short leases and
  a documented degraded mode.
- Observe-only decisions precede deployment and principal enforcement. Each
  switch has a secure default, owner, audit event and tested rollback command.
- Limits are measured with representative synthetic workloads and committed to
  configuration, tests, threat models and runbooks.
