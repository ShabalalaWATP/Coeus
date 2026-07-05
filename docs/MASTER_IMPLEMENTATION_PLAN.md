# Coeus Master Implementation Plan

The authoritative project implementation plan is
`coeus_spec_driven_implementation_plan.md` at the repository root. This file is
the concise delivery tracker and must stay within the repository line limit.

## Current Stage

Sprint 13: Security hardening.

## Delivery Ledger

| Sprint | Scope | Status | Verification |
| --- | --- | --- | --- |
| 1 | Skeleton, monorepo, API/web shells, Compose and quality gates. | Complete | Local backend/frontend/security gates passed on 2026-07-04. |
| 2 | Auth, sessions, RBAC, role navigation, seed users and branch protection docs. | Complete | Local auth, CI and browser gates passed on 2026-07-04. |
| 3 | ACGs, project workspaces, access diagnostics and product/project access policy. | Complete | Local access-control gates passed on 2026-07-04. |
| 4 | Ticket intake, mock chatbot, editable intake, attachments, timeline and customer dashboard. | Complete | Local ticket-intake gates passed on 2026-07-05. |
| 5 | Intelligence Store metadata, search, detail, upload and controlled asset access. | Complete | Local store and access-regression gates passed on 2026-07-05. |
| 6 | Deterministic synthetic product generation and seed manifests. | Complete | Local generator, security and file-line gates passed on 2026-07-05. |
| 7 | RFI Search Agent, hybrid ranking, product offers and search metrics. | Complete | Local RFI search, Semgrep and UI gates passed on 2026-07-05. |
| 8 | RFA/CM routing agents, manager queues, approvals, clarifications and overrides. | Complete | Local routing, Semgrep and UI gates passed on 2026-07-05. |
| 9 | Analyst workbench, assignment, work packages, notes, linked products, drafts and QC submission. | Complete | Local analyst, Semgrep and UI gates passed on 2026-07-05. |
| 10 | QC queue, checklist, rejection, auto-ingestion, indexing, dissemination and feedback requests. | Complete | Local and GitHub backend, frontend, Semgrep and CodeQL gates passed on 2026-07-05. |
| 11 | Feedback submission, admin/RFA/CM dashboards, product reuse analytics and Trends Analysis Agent. | Complete | Local backend, frontend, Semgrep and security gates passed on 2026-07-05. |
| 12 | GCP dev deployment, Terraform baseline, Cloud Run, Cloud SQL, Cloud Storage, Secret Manager, Pub/Sub, Artifact Registry and Gemma config. | Complete | Local backend, frontend, Terraform, Semgrep and security gates passed on 2026-07-05. |

## Sprint 11 Delivered Scope

- Requester feedback request listing and one-time feedback submission.
- Immutable feedback submission records with rating, comment and follow-up flag.
- Admin, RFA and collection analytics endpoints with role-scoped permissions.
- Product reuse analytics over disseminations, accepted offers and feedback.
- Deterministic Trends Analysis Agent insights for region, reuse and satisfaction.
- Customer feedback panel on `/app/requests`.
- Analytics dashboards at `/admin/analytics`, `/rfa/analytics` and
  `/collection/analytics`.
- Sprint 11 spec, ADR and threat model.

## Sprint 11 Verification

- Backend Ruff, mypy and pytest: 101 passed, 95.45 percent total coverage.
- Backend Bandit and pip-audit: passed; local package skipped by pip-audit.
- Frontend Prettier, ESLint and TypeScript: passed. ESLint has existing router
  fast-refresh warnings only.
- Frontend Vitest: 118 passed, 99.92 percent line coverage and 95.06 percent
  branch coverage.
- Frontend production build, Playwright e2e and production dependency audit:
  passed.
- Semgrep full-repository and Sprint 11 targeted scans: 0 findings.
- pnpm supply-chain policy, file line limit and Compose config: passed.

## Sprint 12 Delivered Scope

- Terraform dev baseline under `infra/gcp/environments/dev`.
- Modular Terraform for GCP services, IAM, Artifact Registry, Cloud Run, Cloud
  SQL, Cloud Storage, Secret Manager and Pub/Sub.
- GitHub OIDC Workload Identity Federation without service account keys.
- Manual-first `Deploy Dev` workflow for API and web Cloud Run deployment.
- Production web container image for Cloud Run.
- Runtime settings for GCP, GCS, Pub/Sub and Gemma Vertex configuration.
- Sprint 12 spec, ADR, threat model and GCP dev deployment runbook.

## Sprint 12 Verification

- Backend Ruff, mypy and pytest: 107 passed, 95.50 percent total coverage.
- Backend Bandit and pip-audit: passed; local package skipped by pip-audit.
- Frontend Prettier, ESLint and TypeScript: passed. ESLint has existing router
  fast-refresh warnings only.
- Frontend Vitest: 118 passed, 99.92 percent line coverage and 95.06 percent
  branch coverage.
- Frontend production build, Playwright e2e and production dependency audit:
  passed.
- Terraform fmt and validate: passed with Terraform 1.10.5 and Google provider
  7.39.0.
- Semgrep full-repository scan: 0 findings.
- File line limit and Compose config: passed.

## Sprint 13 Next Scope

- CodeQL and Semgrep hardening review.
- Secret scanning and push protection confirmation.
- Trivy or Grype container scans.
- SBOM generation.
- ZAP baseline.
- Terraform scanning.
- Prompt injection suite.
- Full threat model pass.
- Air-gapped deployment notes.
