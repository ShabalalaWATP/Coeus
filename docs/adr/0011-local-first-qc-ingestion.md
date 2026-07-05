# ADR 0011: Local-First QC Ingestion

## Status

Accepted.

## Context

Sprint 10 must release analyst-produced draft products into the Intelligence
Store without adding a real database, object store, embedding service or queue
worker. The code still needs to preserve the boundaries planned for production:
QC decisions, release checks, product ingestion, indexing, dissemination and
feedback creation should not be hidden inside route handlers.

## Decision

Implement Sprint 10 as a local-first service layer:

- `QualityControlService` coordinates approve and reject decisions.
- `ReleaseCheckService` validates checklist and release metadata.
- `ProductAutoIngestionService` creates a published `StoreProduct` from the
  latest draft.
- `ProductIndexingService` records queued and indexed states to model the future
  asynchronous indexing worker.
- `DisseminationService` records controlled dissemination only after Store
  access policy confirms the requester can read the product.
- `FeedbackRequestService` creates the first requester feedback request record.

QC data remains attached to the ticket aggregate until the persistent storage
phase introduces dedicated tables. Product data is saved through the existing
Store repository so search and access filtering are exercised immediately.

## Consequences

- Sprint 10 stays deterministic and runnable in local tests without cloud
  credentials.
- Production-facing boundaries are explicit and can later receive repositories,
  outbox records and workers without changing the route contract.
- The local indexing implementation is a synchronous simulation of an
  asynchronous worker. This is acceptable for Sprint 10 but must be replaced
  when real queue infrastructure is introduced.
- Dissemination is blocked if ACG metadata would prevent requester visibility,
  reducing the risk of false release records.
