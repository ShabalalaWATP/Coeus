# ADR 0010: Local-First Analyst Workflow

## Status

Accepted.

## Context

Sprint 9 introduces analyst assignment, work packages, notes, linked source
products, draft products and QC submission. The repository remains public-safe
and local-first, and persistent workflow tables are not yet part of the current
sprint.

## Decision

Implement analyst workflow records on the ticket aggregate:

- `AnalystWorkflowService` owns assignment, task visibility, notes, product
  links, work package completion, draft versions and QC submission.
- The service reuses `StoreDetailService` for product-link authorisation instead
  of duplicating ACG or clearance logic.
- Draft products store metadata, content and asset descriptors only. They do not
  write real files.
- `QC_REVIEW` is a terminal state for Sprint 9. QC decisions and automatic
  ingestion are deferred to Sprint 10.
- The frontend uses typed analyst API functions and TanStack Query cache updates
  for task mutations.

## Consequences

- Sprint 9 remains deterministic in local development and CI.
- Product access checks stay centralised in the Store policy.
- Draft versioning and traceability are testable before persistent tables exist.
- Future database-backed workflow tables can replace the in-memory ticket records
  without changing the high-level service boundary.
