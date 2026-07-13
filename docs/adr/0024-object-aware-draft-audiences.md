# ADR 0024: Object-Aware Draft Audiences

## Status

Accepted for Sprint 17, 2026-07-13.

## Context

Deep scan `abf0e143` showed that `PRODUCT_MANAGE_ASSETS` was treated as global
draft relevance. Search, detail and asset access therefore exposed unrelated
same-ACG drafts to product-team and multi-role users. A permission can authorise
an action, but it cannot prove an actor-to-product relationship.

## Decision

- Every draft read requires active identity, `PRODUCT_READ`, sufficient
  classification, an active ACG intersection and an explicit draft-audience
  reason.
- Audience reasons are creator, assigned analyst, responsible workflow manager,
  assigned QC reviewer, Intelligence Store Manager or platform administrator.
- Combining roles never creates an audience reason. `PRODUCT_MANAGE_ASSETS`
  permits asset actions only after audience membership is established.
- Tactical live relationship checks remain authoritative until a persisted,
  indexed audience projection can update atomically with workflow state.
- Search, detail, token grant and token redemption consume the same policy.
- Removing an audience reason invalidates authority immediately. Signed tokens
  are reauthorised at redemption and cannot preserve revoked draft access.
- Ambiguous backfill or projection failure denies access and blocks cutover.

The relational projection records assigned analysts, the manager who made each
active assignment and the QC reviewer who atomically claimed the submission.
Store search, detail and selected-object policy consume that projection and
revoke access when the relationship becomes inactive. Creator access remains
an object field. The shared QC queue exposes only reference, state and claim
status until an eligible QC manager claims an item. Only that reviewer receives
full detail and object-specific draft authority. Claims are retained through
rework and revoked effectively on release, approval or another lifecycle exit.

## Consequences

- Unrelated same-ACG users lose access that was never intended need-to-know
  access; published-product behaviour remains unchanged.
- Store repository queries need actor-specific draft predicates rather than one
  `include_drafts` Boolean.
- Workflow transactions own assignment-derived audience maintenance. Backfill
  reconciliation is dry-run first, serializable and atomically audited. A
  zero-drift release-candidate report and the full matrix remain release gates.
- Tests cover projected analyst, manager and QC access, competing QC claims,
  unrelated denial and revocation. ACG removal, clearance reduction,
  publication and archive remain part of the full Phase 2 acceptance matrix.
