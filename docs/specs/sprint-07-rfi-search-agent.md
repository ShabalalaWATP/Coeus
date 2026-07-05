# Sprint 7 Spec: RFI Search Agent

## Goal

Add the first RFI Search Agent workflow. When a submitted RFI enters
`RFI_SEARCHING`, Coeus searches the access-controlled Intelligence Store,
ranks permitted products, offers useful matches to the requester, and records
safe search metrics.

## In Scope

- Access-filtered RFI product search from submitted ticket intake.
- Deterministic full-text and semantic scoring adapters behind service
  boundaries.
- Hybrid ranking with match explanations.
- Product offers with accept and reject actions.
- Existing-product acceptance that closes the ticket and records dissemination.
- Rejection reason capture that routes the ticket to assessment.
- Search metrics for visible candidates, offers, rejections and acceptances.
- API and UI tests for ranking, access filtering, offer handling and leakage
  controls.

## Out Of Scope

- Persistent PostgreSQL indexes and real pgvector storage. The Sprint 7
  service exposes adapter boundaries so a database-backed implementation can
  replace the deterministic local implementation.
- Real external connectors.
- Final analytics dashboards. Sprint 7 records metrics for later aggregation.
- Real dissemination downloads beyond the existing controlled asset access
  placeholder.

## Acceptance Criteria

- The agent searches only products visible to the ticket requester.
- Full-text and semantic scores are combined into one hybrid score.
- Results below the offer threshold are not offered.
- Archived and draft products are excluded from default RFI offers.
- Product IDs, counts and facets are never returned for products the caller
  cannot read.
- Offers include title, summary, product type, match score, match reasons,
  classification, releasability, region, time period and asset types.
- Accepting an offer closes the ticket as `CLOSED_EXISTING_PRODUCT_ACCEPTED`
  and creates a ticket dissemination record.
- Rejecting the final active offer records a reason and routes the ticket to
  `ROUTE_ASSESSMENT`.
- Search, accept and reject actions are audited.
