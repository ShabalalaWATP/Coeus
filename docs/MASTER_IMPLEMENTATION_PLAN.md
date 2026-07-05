# Coeus Master Implementation Plan

The authoritative project implementation plan is `coeus_spec_driven_implementation_plan.md` at the repository root.

This document tracks delivery state as implementation progresses.

## Current Stage

Sprint 10: QC, dissemination and automatic product ingestion.

## Sprint 1 Scope

- Monorepo.
- FastAPI skeleton.
- React Vite skeleton.
- Docker Compose with PostgreSQL.
- Basic CI.
- 95 percent backend and frontend coverage gates.
- Initial specs and ADRs.
- Initial threat model.

## Sprint 1 Status

- Root workspace and repository metadata: implemented.
- API health and readiness skeleton: implemented.
- Web app shell: implemented.
- Local Compose stack: implemented.
- CI workflows: implemented.
- Initial docs: implemented.
- Verification: passed on 2026-07-04.

## Sprint 1 Verification

- Backend coverage: 99.53 percent total coverage.
- Frontend coverage: 100 percent line coverage and 96.07 percent branch coverage.
- Backend security checks: Bandit completed with no issues; pip-audit found no known vulnerabilities in third-party packages.
- Frontend package audit: no known production dependency vulnerabilities.
- Browser smoke: Playwright Chromium passed.
- Compose config: `docker compose config` validated.

## Sprint 2 Scope

- Login.
- Sessions.
- RBAC.
- Role navigation.
- Seed users.
- Auth audit.
- Branch protection documentation.

## Sprint 2 Status

- Backend auth/session/RBAC foundation: implemented.
- Frontend login and protected routing: implemented.
- Seed users: implemented as a local repository adapter.
- Auth audit: implemented for login success, login failure and logout.
- Branch protection documentation: implemented.
- Verification: passed on 2026-07-04.

## Sprint 2 Verification

- Backend coverage: 96.90 percent total coverage.
- Frontend coverage: 100 percent line coverage and 97.41 percent branch coverage.
- Backend quality checks: Ruff, mypy and pytest passed.
- Frontend quality checks: Prettier, ESLint, TypeScript, Vitest coverage, production build and Playwright Chromium e2e passed.
- Backend security checks: Bandit completed with no issues; pip-audit found no known third-party vulnerabilities; Semgrep scanned tracked and untracked source files with no findings.
- Frontend package audit: no known production dependency vulnerabilities.
- Compose config: `docker compose config` validated.
- Live browser smoke: local API on `127.0.0.1:8001` and Vite on `127.0.0.1:5173` verified admin login to `/admin/overview`, user denial at `/forbidden`, and no auth token in local storage.
- Secret review: changed-file secret-pattern scan found only mock development credentials and expected auth implementation references.

## Sprint 3 Scope

- ACG model.
- ACG admin UI.
- Product and project access policy.
- Project Workspace basics.
- Access diagnostics.
- ACG tests.

## Sprint 3 Status

- Local-first ACG, product and project seed repository: implemented.
- ACG service and admin APIs: implemented.
- Product and project access policies: implemented.
- Project workspace APIs and frontend routes: implemented.
- Access diagnostics: implemented for administrator product access review.
- ACG audit events: implemented for create, update, add member and remove member.
- Sprint 3 spec, ADR and threat model: implemented.
- Verification: passed on 2026-07-04.

## Sprint 3 Verification

- Backend coverage: 97.04 percent total coverage.
- Frontend coverage: 100 percent statement, line and function coverage, with 96.03 percent branch coverage.
- Backend quality checks: Ruff, mypy and pytest passed.
- Frontend quality checks: Prettier, ESLint, TypeScript, Vitest coverage, production build and Playwright Chromium e2e passed.
- Backend security checks: Bandit completed with no issues; pip-audit found no known third-party vulnerabilities; Semgrep scanned tracked source and infrastructure files with no findings.
- Frontend package audit: no known production dependency vulnerabilities.
- Compose config: `docker compose config` validated.

## Sprint 4 Scope

- Ticket model.
- Chat UI.
- Mock LLM provider.
- Intake extraction.
- Ticket creation.
- Customer dashboard.
- Timeline.

## Sprint 4 Status

- Local-first ticket, intake, chat, attachment metadata, agent-run and timeline domain records: implemented.
- In-memory ticket repository behind service boundaries: implemented.
- Mock LLM provider, deterministic intake extraction and completeness checks: implemented.
- Ticket and chat APIs for list, create/resume chat, edit intake, add metadata, submit and add information: implemented.
- Customer request dashboard, chat transcript, editable intake panel, attachment metadata form and timeline: implemented.
- Prompt-injection regression coverage for RBAC bypass, hidden prompt disclosure and fabricated product claims: implemented.
- Sprint 4 spec, ADR and threat model: implemented.
- Verification: passed on 2026-07-05.

## Sprint 4 Verification

- Backend coverage: 95.08 percent total coverage.
- Frontend coverage: 100 percent statement, line and function coverage, with 96.43 percent branch coverage.
- Backend quality checks: Ruff, mypy and pytest passed.
- Frontend quality checks: Prettier, ESLint, TypeScript, Vitest coverage, production build and Playwright Chromium e2e passed. ESLint still reports existing fast-refresh warnings for lazy route declarations in `router.tsx`.
- Backend security checks: Bandit completed with no issues; pip-audit found no known third-party vulnerabilities; Semgrep completed with no findings.
- Frontend package audit: no known vulnerabilities at the configured moderate threshold.
- Compose config: `docker compose config` validated.

## Sprint 5 Scope

- Product metadata model.
- Asset metadata model.
- Store search, detail and controlled asset access APIs.
- Existing-product registration workflow with ACG assignment.
- Metadata suggestions.
- Store search, detail, upload and my-products frontend routes.
- Regression coverage for unauthorised counts, detail IDOR and asset access.

## Sprint 5 Status

- Local-first Intelligence Store domain, repository and service boundaries: implemented.
- Product creation with required ACGs, owner-team permissions, metadata and asset validation: implemented.
- Search filtering after RBAC, clearance and ACG checks: implemented.
- Product detail and controlled placeholder asset access tokens: implemented.
- Metadata suggestions that never auto-assign ACGs: implemented.
- `/store`, `/store/my-products`, `/store/upload`, `/store/products/:productId` and asset routes: implemented.
- Sprint 5 spec, ADR and threat model: implemented.
- Verification: passed locally on 2026-07-05.

## Sprint 5 Verification

- Backend coverage: 95.67 percent total coverage.
- Frontend coverage: 99.90 percent line coverage and 95.43 percent branch coverage.
- Backend quality checks: Ruff, mypy and pytest passed.
- Frontend quality checks: Prettier, ESLint, TypeScript, Vitest coverage, production build and Playwright Chromium e2e passed. ESLint still reports existing fast-refresh warnings for lazy route declarations in `router.tsx`.
- Backend security checks: Bandit completed with no issues; pip-audit found no known third-party vulnerabilities; Semgrep completed with no findings.
- Frontend package audit: no known vulnerabilities at the configured moderate threshold.
- Compose config: `docker compose config` validated.

## Sprint 6 Scope

- Synthetic product generators.
- PDF seed products.
- DOCX seed products.
- Image seed products.
- GeoJSON and KML seed products.
- CSV and JSON seed products.
- Product bundles.
- Seed ACGs.
- Seed access scenarios.

## Sprint 6 Status

- Standard-library mock product generator package: implemented.
- Deterministic PDF, DOCX, PNG, JPEG, GeoJSON, KML, CSV and JSON writers: implemented.
- Product bundle generation: implemented.
- Seed manifest with 190 default products and 410 asset descriptors: implemented.
- Five mock ACG definitions and four named access scenarios: implemented.
- Small seed smoke mode for one product per family: implemented.
- Sprint 6 spec, ADR and threat model: implemented.
- Verification: passed locally on 2026-07-05.

## Sprint 6 Verification

- Backend coverage: 95.67 percent total coverage.
- Frontend coverage: 99.90 percent line coverage and 95.43 percent branch coverage.
- Line limit: all checked hand-written files are 350 lines or fewer.
- Backend quality checks: Ruff, mypy and pytest passed.
- Frontend quality checks: Prettier, ESLint, TypeScript, Vitest coverage, production build and Playwright Chromium e2e passed. ESLint still reports existing fast-refresh warnings for lazy route declarations in `router.tsx`.
- Seed smoke: `python scripts/seed/seed_mock_products.py --small --output-dir .local/mock-products-smoke` generated 7 products and 16 assets with the `MOCK DATA ONLY` banner.
- Backend security checks: Bandit completed with no issues; pip-audit found no known third-party vulnerabilities; Semgrep completed with no findings.
- Frontend package audit: no known vulnerabilities at the configured moderate threshold.
- Codex Security diff scan: completed with 0 findings and 9 of 9 worklist rows closed.
- Compose config: `docker compose config` validated.

## Sprint 7 Scope

- Full-text search.
- pgvector-style semantic search adapter.
- Hybrid ranking.
- Access-filtered search.
- Product offers.
- Accept and reject flow.
- Search metrics.

## Sprint 7 Status

- Local-first RFI Search Agent service: implemented.
- Requester-based Intelligence Store access filtering before ranking: implemented.
- Deterministic full-text, semantic and metadata hybrid ranking: implemented.
- Product-offer records, search metrics and dissemination records: implemented.
- RFI search, results, accept and reject APIs: implemented.
- `/app/requests` product-offer panel with run, accept and reject controls: implemented.
- Sprint 7 spec, ADR and threat model: implemented.
- Verification: passed locally on 2026-07-05.

## Sprint 7 Verification

- Backend coverage: 96.16 percent total coverage.
- Frontend coverage: 99.91 percent line coverage and 95.18 percent branch coverage.
- Line limit: all checked hand-written files are 350 lines or fewer.
- Backend quality checks: Ruff, mypy and pytest passed.
- Frontend quality checks: Prettier, ESLint, TypeScript, Vitest coverage, production build and Playwright Chromium e2e passed. ESLint still reports existing fast-refresh warnings for lazy route declarations in `router.tsx`.
- Backend security checks: Bandit completed with no issues; pip-audit found no known third-party vulnerabilities; Semgrep completed with no findings.
- Frontend package audit: no known production dependency vulnerabilities.
- Compose config: `docker compose config` validated.

## Sprint 8 Scope

- RFA capability agent.
- CM capability agent.
- Manager queues.
- Human approval.
- Clarification flow.
- Project plan update.
- RFA-first and CM-fallback routing.

## Sprint 8 Status

- Local-first RFA and CM capability agents: implemented.
- Structured capability reviews on ticket records: implemented.
- RFA-first routing, CM fallback and clarification route selection: implemented.
- RFA and collection manager queue APIs: implemented.
- Manager approval, rejection, clarification and override actions: implemented.
- Ticket-level project-plan update records and manager decision audit events: implemented.
- `/rfa/queue` and `/collection/queue` manager pages: implemented.
- Sprint 8 spec, ADR and threat model: implemented.
- Verification: complete.

## Sprint 8 Verification

- Backend Ruff: passed.
- Backend mypy: passed.
- Backend pytest: 90 passed, 95.38 percent total coverage.
- Backend Bandit: passed.
- Backend pip-audit: no known vulnerabilities found, local package skipped because it is not published on PyPI.
- Frontend Prettier: passed.
- Frontend ESLint: passed with existing router fast-refresh warnings only.
- Frontend TypeScript: passed.
- Frontend Vitest: 96 passed, 99.92 percent line coverage and 95.77 percent branch coverage.
- Frontend production build: passed.
- Frontend Playwright e2e: 1 passed.
- Frontend production dependency audit: no known vulnerabilities found.
- Semgrep repository scan: 0 findings on tracked files.
- Semgrep Sprint 8 targeted scan: 0 findings on new Sprint 8 backend, frontend and documentation files.
- File line limit: all checked hand-written files are 350 lines or fewer.
- Compose config: `docker compose config` validated.

## Sprint 9 Scope

- Analyst workbench.
- Work packages.
- Notes.
- Link permitted products.
- Draft product.
- Submit to QC.

## Sprint 9 Status

- Manager assignment to active analyst users: implemented.
- Assigned-only analyst task visibility: implemented.
- Work package checklist records and completion actions: implemented.
- Analyst notes: implemented.
- Permitted Intelligence Store product linking: implemented.
- Versioned draft products with asset descriptors: implemented.
- Submit-to-QC transition to `QC_REVIEW`: implemented.
- `/analyst/workbench` and `/analyst/tasks/:taskId` pages: implemented.
- Sprint 9 spec, ADR and threat model: implemented.
- Verification: complete.

## Sprint 9 Verification

- Backend Ruff: passed.
- Backend mypy: passed.
- Backend pytest: 95 passed, 95.32 percent total coverage.
- Backend Bandit: passed.
- Backend pip-audit: no known vulnerabilities found, local package skipped because it is not published on PyPI.
- Frontend Prettier: passed.
- Frontend ESLint: passed with existing router fast-refresh warnings only.
- Frontend TypeScript: passed.
- Frontend Vitest: 100 passed, 99.90 percent line coverage and 95.26 percent branch coverage.
- Frontend production build: passed.
- Frontend Playwright e2e: 1 passed.
- Frontend production dependency audit: no known vulnerabilities found.
- Semgrep repository scan: 0 findings on tracked files.
- Semgrep Sprint 9 targeted scan: 0 findings on new Sprint 9 backend, frontend and documentation files.
- File line limit: all checked hand-written files are 350 lines or fewer.
- Compose config: `docker compose config` validated.
