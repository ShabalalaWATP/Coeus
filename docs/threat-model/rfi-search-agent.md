# Threat Model: RFI Search Agent

## Scope

Sprint 7 RFI search, hybrid ranking, product offers, accept and reject flow,
search metrics and the request-dashboard offer UI.

## Assets

- Product identifiers and metadata in the Intelligence Store.
- Ticket intake content, timelines and product-offer decisions.
- ACG membership, clearance and product visibility decisions.
- Search metrics that could reveal hidden product existence.

## Threats And Controls

| Threat | Control in Sprint 7 |
|---|---|
| Search results or grounded evidence reveal products outside the requester's ACGs. | Search runs as the ticket requester. At commit, the requester must retain an active ACG and the exact initiating session. The transaction locks and revalidates the union of every offered product ID and every product ID in persisted grounded evidence, including evidence products not present in the offers. |
| Counts or metrics reveal hidden product existence. | External result payloads are built from caller-visible offers only. Store facets remain calculated after access filtering. |
| Semantic labels become an access bypass. | Labels are derived metadata only. They are indexed and scored after Store visibility filtering, and product detail still requires RBAC, clearance and at least one active shared ACG. |
| Direct API calls accept or reject unauthorised products. | Accept and reject require ticket ownership, RFI permissions, an existing active offer and a fresh product visibility check. |
| RFI search or offer decisions change a ticket without audit evidence. | Search run, offer acceptance and offer rejection restore the original ticket if audit recording fails after the proposed ticket update. |
| A non-offered evidence product becomes hidden while search is in flight. | The guarded commit treats offered and grounded-evidence IDs as one product authority set. Local race tests prove a visibility change to either set denies persistence without leaking the hidden identifier. |
| Ticket collaborators see restricted RFI matches through the generic ticket response. | `visibleProductMatches` is returned only to the requester. Other viewers must use the RFI results endpoint, which filters offers through their own Store access policy. |
| Prompt-injected intake fabricates product matches. | Product offers are generated only by the RFI Search Agent from store products. User chat text cannot write product IDs into offers. |
| Archived or draft products are offered by default. | RFI search requests published products only. The store access policy still denies drafts unless the actor has management rights. |
| Rejection reason content becomes a script payload in the UI. | Reasons are plain text, length constrained server-side and rendered by React escaping. |
| Search metrics become a covert channel. | Metrics returned to the caller are tied to visible candidates and offers; raw hidden-product counts are not exposed. |
| A weak rank-one match is shown as near-certain relevance. | Absolute lexical and vector evidence determines offer eligibility. Reciprocal-rank fusion contributes only a bounded ordering signal. |
| A reviewer learns the size of the requester's permitted catalogue. | Candidate count is suppressed for actors other than the ticket requester, while every displayed offer is reauthorised for the viewer. |

## Residual Risk

- Deterministic local semantic scoring and labels do not represent production
  embedding quality. Database-backed full-text and pgvector adapters must be
  reviewed before production use.
- PostgreSQL RFI query construction and adapter-specific score calibration need
  a dedicated relevance evaluation set before a production release.
- Dissemination is represented as a ticket record in Sprint 7. Final controlled
  dissemination workflows arrive in the later QC and dissemination sprint.
