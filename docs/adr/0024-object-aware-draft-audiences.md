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

The current relational projection records assigned analysts and the manager who
made each active assignment. Store search, detail and selected-object policy now
consume that projection and revoke access when the assignment becomes inactive.
Creator access remains an object field. A distinct assigned-QC relationship is
not represented by the current workflow model, so that reason remains an
acceptance criterion rather than a claimed implemented projection.

## Consequences

- Unrelated same-ACG users lose access that was never intended need-to-know
  access; published-product behaviour remains unchanged.
- Store repository queries need actor-specific draft predicates rather than one
  `include_drafts` Boolean.
- Workflow transactions own assignment-derived audience maintenance. Backfill
  reconciliation and shadow-comparison evidence remain release gates.
- Tests cover projected analyst/manager access, unrelated denial and revocation.
  QC assignment, ACG removal, clearance reduction, publication and archive stay
  in the full Phase 2 acceptance matrix and must not be inferred from this slice.
