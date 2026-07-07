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
| Search results reveal products outside the requester's ACGs. | The RFI Search Agent searches as the ticket requester and builds offers only from store results that have already passed RBAC, clearance, ACG and status checks. |
| Counts or metrics reveal hidden product existence. | External result payloads are built from caller-visible offers only. Store facets remain calculated after access filtering. |
| Semantic labels become an access bypass. | Labels are derived metadata only. They are indexed and scored after Store visibility filtering, and product detail still requires RBAC, clearance and at least one active shared ACG. |
| Direct API calls accept or reject unauthorised products. | Accept and reject require ticket ownership, RFI permissions, an existing active offer and a fresh product visibility check. |
| Ticket collaborators see restricted RFI matches through the generic ticket response. | `visibleProductMatches` is returned only to the requester. Other viewers must use the RFI results endpoint, which filters offers through their own Store access policy. |
| Prompt-injected intake fabricates product matches. | Product offers are generated only by the RFI Search Agent from store products. User chat text cannot write product IDs into offers. |
| Archived or draft products are offered by default. | RFI search requests published products only. The store access policy still denies drafts unless the actor has management rights. |
| Rejection reason content becomes a script payload in the UI. | Reasons are plain text, length constrained server-side and rendered by React escaping. |
| Search metrics become a covert channel. | Metrics returned to the caller are tied to visible candidates and offers; raw hidden-product counts are not exposed. |

## Residual Risk

- Deterministic local semantic scoring and labels do not represent production
  embedding quality. Database-backed full-text and pgvector adapters must be
  reviewed before production use.
- Dissemination is represented as a ticket record in Sprint 7. Final controlled
  dissemination workflows arrive in the later QC and dissemination sprint.
