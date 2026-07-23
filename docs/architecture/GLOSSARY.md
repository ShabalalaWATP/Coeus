# Architecture Glossary

These terms are canonical across the architecture atlas.

## Product and work

| Term             | Meaning                                                                                        |
| ---------------- | ---------------------------------------------------------------------------------------------- |
| Istari           | Product name shown to users.                                                                   |
| Coeus            | Repository, package and infrastructure working name.                                           |
| Request          | User-facing name for a requirement tracked internally as a ticket.                             |
| Ticket           | Versioned workflow aggregate that carries intake, routing, tasking, product and outcome state. |
| Product          | Intelligence Store record with metadata, access scope and zero or more protected assets.       |
| Draft version    | Immutable analyst submission identified by version, size and SHA-256 digest.                   |
| Released product | QC-approved, published Store product with controlled dissemination.                            |
| RFI              | Request for information: search existing authorised products before new tasking.               |
| RFA              | Request for assessment: analysis or assessment work owned by an RFA team.                      |
| CM               | Collection management: collection work owned by a CM team.                                     |
| JIOC             | Joint Intelligence Operations Centre function that routes, oversees and adjudicates work.      |
| Store            | Intelligence Store catalogue, search, metadata and controlled asset access.                    |

## People and authority

| Term                        | Meaning                                                                                                                   |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Customer                    | Account role that creates and owns requests.                                                                              |
| Requester                   | Relationship to one ticket, normally the Customer who created it.                                                         |
| Collaborator                | Ticket-scoped viewer or editor; not a standalone role.                                                                    |
| Delegated ACG administrator | Group-specific responsibility that can review applications; not an application role and not content access by itself.     |
| In the loop                 | A human decision is required before the workflow can continue.                                                            |
| On the loop                 | A human monitors deterministic automation and can intervene through explicit controls.                                    |
| Separation of duties        | A live policy that prevents the same person approving their own authority-bearing work even when multiple roles are held. |

## Security and data

| Term                  | Meaning                                                                                                                      |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| ACG                   | Access control group used with clearance and status to enforce need-to-know.                                                 |
| Clearance             | Numeric account attribute compared with product classification.                                                              |
| Need-to-know          | Current permission, clearance, ACG, status and draft-audience predicates applied to an object and action.                    |
| Break-glass           | Audited restricted-read path requiring a reason and separate permission; it does not silently weaken normal policy.          |
| Compatibility state   | Allowlisted JSONB namespaces in `coeus_state` used for bounded repositories not yet fully relational.                        |
| Workflow authority    | Versioned relational ticket aggregate, current actor and object policy, audit evidence and outbox intent committed together. |
| Outbox                | Durable post-commit intent table with fenced claims, retries and dead-letter state.                                          |
| Derived index         | Rebuildable search data that is not part of the logical recovery bundle.                                                     |
| Store browse index    | Compatibility product projection using lexical search and 384-dimensional vectors.                                           |
| Grounded search index | Provider/model/generation-aware chunks and open-ticket documents using 1,536-dimensional vectors.                            |

## Status labels

| Label        | Meaning                                                                            |
| ------------ | ---------------------------------------------------------------------------------- |
| Implemented  | Shipped and represented by current code.                                           |
| Optional     | Shipped but inactive until explicitly configured.                                  |
| Limitation   | Current behaviour or an unresolved implementation constraint, not a target design. |
| Future gated | Reference target blocked by explicit readiness controls or missing adapters.       |
| Historical   | Preserved evidence or superseded design, not current operating guidance.           |
