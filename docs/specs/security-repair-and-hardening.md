# Security repair and secure-design hardening

## Status

Implementation complete for the supported local-first boundary. This document
preserves the Sprint 17 acceptance contract, not the latest scan baseline.
Production remains blocked by authorised staging verification and a fresh
sealed whole-repository deep scan of the exact immutable release candidate,
with no unresolved baseline occurrence or new reportable finding.

## Purpose

Close the 12 findings and four deferred questions from deep scan
`abf0e143-4656-4646-b133-6fea0d6661ee`, improve SOLID boundaries and reconcile
the project documentation without removing or changing intended functionality.
The detailed implementation sequence is in the
[historical repair plan](../security/SECURITY_REPAIR_AND_HARDENING_PLAN.md).

## Required Behaviour

### Draft product access

- Draft search, detail, asset grant and token redemption use one object-aware
  audience policy in addition to ACG, clearance and lifecycle checks.
- Creators, assigned analysts, authorised managers, QC and administrators keep
  only their documented access.
- Unrelated same-ACG and multi-role users cannot discover or download drafts.
- Removing an audience relationship removes its authority immediately.

### Request and resource admission

- Anonymous or security-rejected multipart bodies cause zero multipart spool
  writes before the response, including chunked bodies without content length.
- Accepted uploads are streamed to staged storage without full-payload heap
  duplication and are promoted atomically.
- LLM, embedding, search, upload and retained-ticket work is bounded by
  principal and deployment budgets before expensive work starts.
- Reservations commit, refund and expire exactly once across failure, timeout,
  cancellation and process restart.
- Authentication throttling retains a bounded amount of state for every source.

### Workflow integrity

- Every state transition commits against the exact version it validated.
- Requester cancellation and QC release cannot both commit from one snapshot.
- Release, product linkage, dissemination, feedback request and durable outbox
  intent commit atomically.
- One ticket mutation has cost proportional to that ticket rather than the
  retained corpus.
- Existing stored synthetic data survives additive migration and rollback.

### Architecture and maintainability

- Domain, repository and persistence modules do not import service modules.
- Services depend on focused application ports and concrete wiring stays in
  composition.
- Persistence uses stable type identities that survive module refactoring.
- Manual rollback choreography is replaced by typed unit-of-work boundaries.
- Broad backend modules and frontend controllers are split behind compatibility
  facades and characterisation tests.
- Frontend request and response types are generated or mechanically verified
  from OpenAPI.

### Compatibility

- Existing intended API paths, request fields, successful response shapes,
  workflow states, routes, labels and role journeys remain compatible.
- New conflict or limit responses occur only at the documented security
  boundary.
- Local development, mock providers and supported persistence adapters continue
  to work according to their documented support level.
- No migration uses two independently authoritative writers or destructive
  rollback.

### Documentation and operations

- The root plan, master tracker, development story and feature-spec statuses
  identify the same current delivery state.
- ADRs define draft audience, resource accounting, workflow transactions and
  product releasability or handling-caveat policy.
- Threat models and runbooks cover new boundaries, residual risks, migration,
  quota tuning, reconciliation, rollback, lease recovery and outbox replay.
- CI documentation matches executable workflows and all relative Markdown links
  resolve.
- Local, staging and production evidence are labelled accurately.

## Verification

- All 12 original PoCs fail safely and their legitimate positive paths pass.
- The four deferred proxy, CORS and product-policy questions have documented,
  tested conclusions.
- Backend and frontend line and branch coverage each remain at least 95 percent;
  security-sensitive changed modules maintain 100 percent branch coverage unless
  a specifically unreachable branch has a reviewed exclusion.
- OpenAPI semantic comparison reports no unapproved breaking change.
- Empty and seeded PostgreSQL migration, repeatable backfill, reconciliation,
  concurrency, code rollback and backup-restore tests pass.
- A real-stack browser workflow covers request creation through publication and
  exact asset-byte access. The current PostgreSQL workflow also covers one
  unrelated same-ACG search, known-object detail and asset-grant denials plus
  `413` and `429` input-preserving recovery. The remaining audience matrix and
  concurrent `409` browser journey remain release gates.
- All formatting, linting, typing, contract, dead-code, build, dependency,
  security, container, infrastructure and 350-line checks pass.
- A fresh sealed deep scan of the exact clean release candidate has no unresolved
  baseline occurrence and no new reportable finding.
- Authorised staging closes the deferred proxy, CORS and ingress questions;
  without that boundary Sprint 17 remains explicitly blocked.

## Historical eight-finding tranche

Sealed standard review `87a10d13-14af-48cc-a361-72470abc8d8d` of later revision
`752d32a` became the then-current baseline. It added eight findings covering
publication authority, two session races, ticket submission authority, login
and registration Argon2 exhaustion, failed browser logout and self-authorising
draft links. The cross-cutting acceptance contract is
`security-review-remediation-2026-07-14.md`.

This tranche deliberately changes one API default: omitted Store creation
status now means `draft`, while explicit `published` may return `403` when the
actor lacks `product:publish`. Generated contracts and compatibility evidence
must record that approved secure-default change. All eight original PoCs,
bypass variants and legitimate paths must pass in addition to the historical
12-finding matrix. The clean-candidate deep scan and authorised staging gates
above remain unchanged.
