# Coeus Master Implementation Plan

The authoritative project implementation plan is
`coeus_spec_driven_implementation_plan.md` at the repository root. This file is
the concise delivery tracker and must stay within the repository line limit.

## Current Stage

Sprint 15: JIOC workflow restructure delivered (roles, JIOC routing, collect
choice, manager approval, QC-owned release, CM-to-RFA leg, multi-analyst,
teams/profiles/calendars). Sprint 14B security remediation closure continues
in parallel.

## Delivery Ledger

| Sprint | Scope | Status | Verification |
| --- | --- | --- | --- |
| 1 | Skeleton, monorepo, API/web shells, Compose and quality gates. | Complete | Local backend/frontend/security gates passed on 2026-07-04. |
| 2 | Auth, sessions, RBAC, role navigation, seed users and branch protection docs. | Complete | Local auth, CI and browser gates passed on 2026-07-04. |
| 3 | ACGs, product access diagnostics and product access policy. | Complete | Local access-control gates passed on 2026-07-04; legacy workspace surface retired by ADR 0018. |
| 4 | Ticket intake, mock chatbot, editable intake, attachments, timeline and customer dashboard. | Complete | Local ticket-intake gates passed on 2026-07-05. |
| 5 | Intelligence Store metadata, search, detail, upload and controlled asset access. | Complete | Local store and access-regression gates passed on 2026-07-05. |
| 6 | Deterministic synthetic product generation and seed manifests. | Complete | Local generator, security and file-line gates passed on 2026-07-05. |
| 7 | RFI Search Agent, hybrid ranking, product offers and search metrics. | Complete | Local RFI search, Semgrep and UI gates passed on 2026-07-05. |
| 8 | RFA/CM routing agents, manager queues, approvals, clarifications and overrides. | Complete | Local routing, Semgrep and UI gates passed on 2026-07-05. |
| 9 | Analyst workbench, assignment, work packages, notes, linked products, drafts and QC submission. | Complete | Local analyst, Semgrep and UI gates passed on 2026-07-05. |
| 10 | QC queue, checklist, rejection, auto-ingestion, indexing, dissemination and feedback requests. | Complete | Local and GitHub backend, frontend, Semgrep and CodeQL gates passed on 2026-07-05. |
| 11 | Feedback submission, admin/RFA/CM dashboards, product reuse analytics and Trends Analysis Agent. | Complete | Local backend, frontend, Semgrep and security gates passed on 2026-07-05. |
| 12 | Inactive future GCP migration reference: Terraform, Cloud Run, Cloud SQL, Cloud Storage, Secret Manager, Pub/Sub, Artifact Registry and AI provider configuration. | Reference complete, inactive | Reference validation passed on 2026-07-05; no live GCP runtime is supported or required. |
| 13 | Security hardening, container scans, SBOM, DAST, Terraform scanning, prompt-injection suite and air-gapped notes. | Complete | Local backend, frontend, Semgrep, Checkov and Gitleaks gates passed on 2026-07-05; Docker-backed checks run in GitHub Actions. |
| 14 | Close the original 2026-07-10 security findings and improve SOLID boundaries, maintainability, independent coverage gates and real integration testing. | Reopened by sealed scan | The implementation gates passed, but the sealed scan of `72a0dc58` reported 16 new reportable findings. |
| 14B | Remediate the sealed 16-finding baseline, verification findings and quality debt, then produce a clean immutable release candidate. | In progress | The original 16 are closed at `7165e49e`. Verification scan `a089e83c` found three Low/P3 findings; their post-scan fixes await full gates and a final seal. |
| 15 | JIOC workflow restructure: role renames plus JIOC Team Member, JIOC routing queue, customer collect choice, manager approval chain, QC-owned release with the CM-to-RFA analysed-collect leg, multi-analyst assignment, teams/profiles/availability calendars, and the permission-refresh-on-restore fix. | Complete | Backend and web suites green at the 95% gates on 2026-07-11; contracts, line-limit, lint and format clean; all four phases verified live in the browser. See ADR 0022 and `docs/specs/jioc-workflow-restructure.md`. |

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

## Sprint 12 Future Reference Scope

- Terraform dev baseline under `infra/gcp/environments/dev`.
- Modular Terraform for GCP services, IAM, Artifact Registry, Cloud Run, Cloud
  SQL, Cloud Storage, Secret Manager and Pub/Sub.
- GitHub OIDC Workload Identity Federation without service account keys.
- Manual migration-reference workflow for Terraform validation and local image
  builds only; no active cloud deployment path.
- Production web container image for Cloud Run.
- Runtime settings for GCP, GCS, Pub/Sub and supported AI provider configuration.
- Sprint 12 spec, ADR, threat model and GCP dev deployment runbook.

This material is not a supported current deployment target. Coeus remains a
local, single-instance application until the readiness gates in ADR 0019 pass.

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

## Sprint 14 Delivered Scope

- Closed 16 original exploit paths and contained the unsupported multi-replica
  session primitive behind local, runtime, IaC and migration-readiness gates.
- Centralised actor-scoped linked-product response policy and bounded analyst
  task, linked-product, similarity and Store projection work.
- Added append-only audit stores, per-username compare-and-restore lockout
  state, atomic registration capacity and decisions, and exact-byte QC assets.
- Split application composition, introduced narrow access, Store and object
  storage protocols, decomposed analyst UI orchestration, and consolidated the
  frontend request transport.
- Replaced the dormant cloud deploy workflow with validation and local image
  builds only, plus a default-deny Terraform migration gate.
- Added separate backend line and branch gates and a real local-stack browser
  flow.

## Sprint 14 Verification Before Security Seal

- Backend Ruff, mypy and pytest: 490 passed, 98.28 percent line coverage and
  95.05 percent branch coverage.
- Frontend Prettier, ESLint, TypeScript and Vitest: 322 passed, 98.77 percent
  line coverage and 95.54 percent branch coverage.
- Frontend Knip, production build, pnpm production audit and the 350-line gate:
  passed.
- Playwright Chromium: 3 passed, including a real Vite-to-FastAPI login and
  request-creation flow without API interception.
- Bandit, pip-audit, Semgrep tracked and untracked scans, Gitleaks changed
  content, Actionlint and Checkov: passed with no reportable finding.
- Terraform 1.10.5: format and validate passed; migration gate 1 of 1 and
  single-writer module tests 3 of 3 passed.
- API container rebuilt; Trivy found zero high or critical vulnerabilities
  when ignoring unfixed issues.

## Sprint 14B Remediation Ledger

The sealed scan of revision `72a0dc58` supersedes the pre-seal completion
claim. Its reportable baseline is:

- P2: exposed local-network PostgreSQL superuser, blocking Store embeddings
  and unbounded chat history.
- P3: blocking RFI embeddings, buffered asset downloads, corpus-linear Store
  embeddings, hybrid and RFI matcher stalls, readiness connection fan-out,
  unbounded product assets, attachment metadata and analyst drafts,
  unpaginated ticket and routing collections, audit pagination loss and a
  false-green ZAP gate.

Revision `7165e49e` integrated the feature slice, passed the full local gates
and closed all 16 baseline findings. The sealed verification scan
`a089e83c-afc7-4213-8763-4a5e5759598d` then found three Low/P3 issues:

- chat and intake saves were not failure-atomic with central audit append;
- an offloaded RFI worker could overwrite a newer authorised ticket update.

The current fix uses a repository-locked save-plus-confirmation boundary,
optimistic ticket snapshot compare-and-swap, conditional rollback, cursor-based
compact request summaries and an explicit browser-dictation privacy notice.
Completion still requires full local gates and a zero-finding sealed scan of a
clean post-fix revision.

## Sprint 13 Delivered Scope

- CodeQL extended and security-and-quality queries.
- Semgrep `auto` plus OWASP Top 10 scanning.
- Gitleaks committed-history scan and documented GitHub push protection.
- Trivy API and web container image scanning with SARIF upload.
- CycloneDX SBOM generation.
- ZAP baseline against a local CI-hosted web target.
- Checkov Terraform scan with SARIF upload.
- Terraform hardening for KMS, Cloud SQL logging, OIDC trust and bucket logs.
- Prompt-injection regression suite.
- Sprint 13 spec, ADR, threat model and air-gapped deployment runbook.

## Sprint 13 Verification

- Backend Ruff, mypy and pytest: 113 passed, 95.59 percent total coverage.
- Backend Bandit and pip-audit: passed; local package skipped by pip-audit.
- Frontend Prettier, ESLint and TypeScript: passed. ESLint has existing router
  fast-refresh warnings only.
- Frontend Vitest: 118 passed, 99.92 percent line coverage and 95.06 percent
  branch coverage.
- Frontend production build, Playwright e2e and production dependency audit:
  passed.
- Terraform fmt, init and validate: passed with Terraform 1.10.5 and Google
  provider 7.39.0.
- Checkov Terraform scan: 118 passed, 0 failed, 2 documented skips.
- Semgrep hardened scan: 0 findings.
- Gitleaks committed-history scan: no leaks found.
- File line limit and Compose config: passed.
