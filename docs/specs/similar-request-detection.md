# Similar Request Detection

## Status

Part B implementation specification. This document was written before the Part B
code changes.

## Problem

Istari currently checks whether an existing intelligence product can satisfy a
request, but it does not check whether another open request is already asking
for substantially the same work. Two near-duplicate requests can therefore move
through RFI search, route assessment, analyst assignment, QC and release in
parallel.

The feature must surface likely overlap without leaking ticket existence across
need-to-know boundaries and without preventing a customer from continuing their
own request.

## Goals

- Detect similar open tickets when a customer submits a complete intake.
- Give customers an advisory "similar request in progress" notice when they may
  already view the matching ticket.
- Let customers join a visible similar ticket as a viewer, or continue their own
  request.
- Show managers similar open requests in the RFA and CM routing queue before
  they decide the route.
- Let managers link two tickets as related, recording the relationship on both
  timelines and in the audit log.
- Reuse the Part A deterministic hybrid retrieval approach, including lexical
  and vector reasons, while keeping tests fully offline.

## Non-Goals

- Do not block submission or route decisions.
- Do not create a separate ticket embedding store.
- Do not add a vector database or background worker.
- Do not let customers see tickets that `get_visible_ticket` would hide.
- Do not merge or cancel duplicate tickets automatically.

## Open Ticket Scope

Similarity checks include tickets in these active workflow states:

- `RFI_SEARCHING`
- `RFI_MATCH_OFFERED`
- `ROUTE_ASSESSMENT`
- `RFA_MANAGER_REVIEW`
- `CM_MANAGER_REVIEW`
- `ANALYST_ASSIGNMENT`
- `ANALYST_IN_PROGRESS`
- `QC_REVIEW`
- `REWORK_REQUIRED`
- `MANAGER_RELEASE`
  The source ticket itself is excluded. Draft, cancelled and closed states are
  excluded, including `DRAFT_INTAKE`, `INFO_REQUIRED`, `CANCELLED`,
  `CLOSED_EXISTING_PRODUCT_ACCEPTED` and `CLOSED_DELIVERED`.

## Scoring

The similarity service compares `query_text(intake)` for the source ticket with
`query_text(intake)` for each open ticket.

Signals:

- Lexical leg: token overlap score from the Part A lexical scorer.
- Semantic leg: cosine similarity between the source and candidate intake
  embeddings when the configured embedding provider returns both vectors.
- Fusion: Reciprocal Rank Fusion with `k = 60`, normalised to 0..1.
- Metadata tie-breaks: small deterministic boosts for region and output-format
  overlap.

Thresholds:

- `0.58` customer notice threshold.
- `0.50` manager queue threshold.

The customer threshold is deliberately higher because customer surfacing can
disclose the existence of another request when the customer already has
visibility. The manager threshold is lower because managers have workflow read
permissions and need a broader consolidation signal before route approval.

Reasons:

- `similarity:lexical-rank:N`
- `similarity:vector:0.83`
- `similarity:metadata-region`
- `similarity:metadata-format`
- `similarity:lexical-only`

Provider failures follow Part A behaviour. If the embedding provider cannot
produce a vector, the service logs one structured warning through the embedding
service and falls back to lexical plus metadata scoring.

## Customer Visibility

Customer-facing disclosure reuses `TicketService.get_visible_ticket`.

For each above-threshold match:

1. Call the existing ticket visibility policy for the current customer.
2. If visible, return ticket reference, title, state, score and reasons.
3. If not visible, do not return any ticket-specific detail.

When hidden matches exist but no visible match exists, the customer receives a
neutral notice:

> The assessing team will check for overlapping work.

That notice confirms only that the overlap check ran. It does not confirm the
number, existence, reference, title, owner or state of hidden tickets.

## Customer Actions

The notice gives the customer two actions:

- Join a visible matching ticket as a viewer. This adds the customer to the
  matching ticket using the same collaborator model and records
  `ticket_collaborator_added` and `similar_request_joined` audit events.
- Continue with the submitted request. This is advisory and is always allowed.

Continuing does not need a backend state transition because submission has
already placed the customer ticket in `RFI_SEARCHING`; it simply dismisses the
notice in the UI.

## Manager Visibility

RFA and CM managers already have workflow read permissions. The routing queue
therefore calls a dedicated similar-request endpoint for the selected ticket and
shows matching open tickets regardless of whether the requester could see them.

Managers see:

- reference
- title
- state
- score
- reasons
- whether the pair is already linked

## Manager Link Action

Managers can link a queue ticket to a similar open ticket. The action:

- requires the same workflow read permission that allows route queue access;
- is idempotent;
- appends `related_ticket_linked` timeline entries to both tickets;
- records a `tickets_linked` audit event;
- returns the refreshed similar-request list.

The link is represented by reciprocal ticket IDs on each ticket record, not by
free-text timeline parsing.

## UX

Customer workspace:

- After submit, if visible matches exist, show a compact notice above the RFI
  search controls.
- Provide "Join as viewer" and "Continue request" buttons.
- If only hidden matches exist, show the neutral assessing-team notice.
- Use the shared mutation error helper for failed join actions.

Routing queue:

- Each selected ticket shows a "Similar open requests" panel before route
  decision controls.
- The panel lists score and reasons.
- A "Link as related" button is disabled when already linked.
- Failed link actions use the shared mutation error helper.

## Audit Events

- `similar_request_notified`: recorded when customer-facing similarity is
  surfaced. Metadata includes the source ticket ID and visible match IDs, or a
  `hidden_matches` count with no ticket identifiers.
- `tickets_linked`: recorded when a manager links two tickets. Metadata includes
  both ticket IDs and `already_linked` for idempotent repeats.

## Performance

The open-ticket set is expected to be hundreds of tickets in local and early
production use. The service therefore scores in memory against hydrated open
tickets from the existing ticket repository. No second embedding table is added
for tickets.

If open-ticket counts grow large enough to require persistence, ticket intake
vectors should live alongside ticket state and be invalidated whenever intake
fields change. That is explicitly deferred until measured need exists.

## Security Invariants

- Customer disclosure never bypasses `get_visible_ticket`.
- Manager disclosure requires workflow read permissions.
- Hidden customer matches never reveal ticket identifiers or counts in the UI.
- Embedding provider defaults remain offline and deterministic.
- Gemini content is sent for ticket similarity only when
  `COEUS_EMBEDDING_PROVIDER=gemini_api` is explicitly selected.
