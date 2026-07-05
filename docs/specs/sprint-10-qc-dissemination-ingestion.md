# Sprint 10 Spec: QC, Dissemination And Automatic Product Ingestion

## Scope

Add the first quality-control workflow for analyst-produced draft products.
Sprint 10 starts when a ticket reaches `QC_REVIEW` and ends when a QC manager
approves and releases the generated product, or rejects it for analyst rework.

## In Scope

- QC queue for submitted analyst products.
- Product preview and draft metadata review.
- Required QC checklist completion before approval.
- Approval and rejection actions.
- Rework state for rejected products.
- Automatic Intelligence Store product creation from the approved draft.
- Local asynchronous indexing records.
- Controlled dissemination to the requester.
- Feedback request creation after dissemination.
- Frontend routes `/qc/queue` and `/qc/products/:productId`.

## Out Of Scope

- Final feedback submission and analytics. Those start in Sprint 11.
- Persistent database tables for QC records. Sprint 10 keeps local-first records
  on ticket aggregates.
- Real asset storage or real embedding infrastructure. Sprint 10 stores only
  synthetic asset metadata and deterministic local indexing records.
- Production deployment changes.

## Acceptance Criteria

- QC managers can see submitted products in a queue.
- QC managers can review the latest draft, manager notes, release metadata and
  required checklist items.
- Approval fails until every checklist item is complete.
- The analyst who drafted the product cannot approve it.
- Users without QC approval permission cannot approve or disseminate a product.
- Rejection records a QC decision and moves the ticket to `REWORK_REQUIRED`.
- Assigned analysts can update a rejected task and resubmit it to QC.
- Approval creates a published Intelligence Store product from the latest draft.
- Approval applies QC-confirmed ACG metadata plus project ACG metadata.
- Approval records queued and indexed product index states.
- Dissemination is recorded only after the requester can read the product.
- A feedback request is created for the requester.
- The disseminated product is searchable by the requester when the ACG policy
  permits it.

## Test Expectations

- Backend API tests cover approval, rejection, separation of duties, automatic
  Store creation, ACG assignment, dissemination, feedback request creation and
  post-index search visibility.
- Frontend tests cover approve, reject, empty queue and API-client calls.
- Existing analyst tests continue to prove QC submission and now allow rework
  resubmission from `REWORK_REQUIRED`.
