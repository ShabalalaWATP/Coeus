# Threat Model: QC Dissemination And Ingestion

## Scope

Sprint 10 QC review, checklist approval, rejection to analyst rework,
automatic Intelligence Store ingestion, local indexing, dissemination and
feedback request creation.

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
| Non-QC user approves or disseminates a product. | QC approval, rejection, product creation and dissemination each check explicit permissions. |
| Product is released without complete QC checks. | `ReleaseCheckService` requires all nine checklist keys to pass before approval. |
| Product is disseminated but the requester cannot read it. | `DisseminationService` calls Store visibility checks for the requester before recording dissemination. |
| Product is indexed with incomplete or inactive ACG metadata. | Release metadata requires at least one active ACG, then merges QC-confirmed ACGs with project ACGs. |
| Rejection loses reviewer rationale. | Rejection creates an immutable ticket-level QC decision and timeline event before moving to `REWORK_REQUIRED`. |
| Draft-only product appears in Store search. | Only approval writes a published Store product. Drafts remain ticket-local before QC approval. |
| QC approval or rejection is saved even though the audit event failed. | Approval and rejection restore the original ticket state if audit recording fails. Approval also discards the ingested Store product and local placeholder asset bytes so the operation can be retried cleanly. |
| Real intelligence or real asset bytes enter the repo. | Sprint 10 stores synthetic metadata only. Tests and docs continue to use `MOCK DATA ONLY` examples. |

## Residual Risks

- Local indexing is a deterministic in-process simulation. Production needs an
  idempotent outbox-backed worker with retry and dead-letter handling.
- Feedback submission, feedback abuse controls and trend analytics are deferred
  to Sprint 11.
- Persistent audit immutability depends on later database-backed storage.
