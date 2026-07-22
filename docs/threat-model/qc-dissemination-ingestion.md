# Threat Model: QC Dissemination And Ingestion

## Scope

Sprint 10 QC review, extended by Sprint 17 assigned-reviewer self-claim,
checklist approval, rejection to analyst rework, automatic Intelligence Store
ingestion, local indexing, dissemination and feedback request creation.

## Assets

- Draft product content and synthetic asset metadata.
- QC decisions and checklist answers.
- Product ACG assignments, releasability and handling caveats.
- Dissemination records and feedback requests.
- Store search visibility for approved products.

## Threats And Controls

| Threat | Control In Sprint 10 |
| --- | --- |
| Analyst approves their own draft. | `QualityControlService` compares the latest draft author with the QC actor and blocks self-approval. |
| Every QC-role user can read every submitted draft. | The shared queue contains only a non-sensitive summary. Full detail and linked-draft audience require an atomic claim by one active QC-team manager. Direct routes return a non-enumerating `404` to other reviewers. |
| Two reviewers concurrently claim or decide the same submission. | Ticket compare-and-swap produces one claimant. Claim and audit commit atomically in local mode and with the relational workflow transaction in PostgreSQL. Competing reviewers receive `409 qc_already_claimed`. |
| A reviewer claims work they authored or analysed. | Claim, detail and decision paths reject any reviewer who authored a draft or holds an active analyst assignment. |
| A released claim leaves stale draft authority. | Draft audiences are derived from the active reviewer and lifecycle. Release or lifecycle exit removes the relationship, and subsequent search/detail checks deny access. |
| A non-QC or concurrently revoked reviewer approves or disseminates a product. | QC approval and rejection require explicit permissions. Guarded release confirms the exact initiating session, live reviewer, QC-team membership, draft access, release-ACG authority and recipient visibility. Another session cannot preserve the operation; restoring the exact initiating session is the positive control. PostgreSQL and local workflow and submission paths use the canonical users, sessions, access, teams, products, ticket lock order. Publication, indexing, dissemination and audit effects occur only after confirmation. |
| Product is released without complete QC checks. | `ReleaseCheckService` requires all nine checklist keys to pass before approval. |
| Product is disseminated but the requester cannot read it. | `DisseminationService` calls Store visibility checks for the requester before recording dissemination. |
| Product is indexed with incomplete or inactive ACG metadata. | Release metadata requires at least one active ACG and accepts only QC-confirmed active ACGs the reviewer is allowed to use. |
| Rejection loses reviewer rationale. | Rejection creates an immutable ticket-level QC decision and timeline event before moving to `REWORK_REQUIRED`. |
| Draft-only product appears in Store search. | QC approval writes published workflow products. The separate existing-product ingestion path can publish only for an actor with `product:publish`; otherwise it defaults to draft. Ticket-local analyst drafts remain outside Store publication before approval. |
| QC approval or rejection is saved even though the audit event failed. | Approval and rejection restore the original ticket state if audit recording fails. Approval also discards the ingested Store product and local placeholder asset bytes so the operation can be retried cleanly. |
| Real intelligence or real asset bytes enter the repo. | Sprint 10 stores synthetic metadata only. Tests and docs continue to use `MOCK DATA ONLY` examples. |

## Residual Risks

- Local indexing is deterministic and in-process. Hosted release notifications
  use the durable outbox, while a production search-index worker still needs
  operational retry and dead-letter evidence.
- Ninety-nine local workflow authority tests, four focused real-PostgreSQL
  authority tests and the unified PostgreSQL lock-order suite at 5/5 pass.
  The database suite includes QC session-deletion denial and restored-session
  success; local QC session races also pass.
  Full backend closure and a clean-revision security rescan remain open.
- Feedback submission, feedback abuse controls and trend analytics are deferred
  to Sprint 11.
- Persistent audit immutability depends on later database-backed storage.
