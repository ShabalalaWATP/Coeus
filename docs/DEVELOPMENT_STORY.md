# Coeus Development Story

## 2026-07-04

- Started Sprint 1 from `coeus_spec_driven_implementation_plan.md`.
- Initialised the local Git repository on `main` and configured `origin` as `https://github.com/ShabalalaWATP/coeus.git`.
- Added the monorepo skeleton for `apps/api`, `apps/web`, `packages`, `infra`, `docs`, `scripts` and GitHub automation.
- Added FastAPI health/readiness foundation, structured logging, request IDs and security headers.
- Added the React/Vite app shell with dark default theme, theme switching, navigation, command bar, notification area and profile control.
- Added local Docker Compose services for PostgreSQL with pgvector and MinIO.
- Added CI foundations for backend, frontend and CodeQL.
- Verified Sprint 1 gates: backend formatting, linting, mypy, pytest coverage, Bandit, pip-audit; frontend formatting, linting, typecheck, Vitest coverage, build, Playwright smoke and production dependency audit.

## 2026-07-04 Sprint 2

- Added local-first authentication with Argon2id seed-user password hashing, server-side sessions, HTTP-only SameSite cookies, CSRF validation, session rotation, lockout and disabled-user blocking.
- Added backend RBAC dependencies and protected admin/audit endpoints.
- Added auth audit events for login success, login failure and logout.
- Added `/login`, `/forbidden` and `/session-expired` frontend routes, protected app routes and backend-driven role navigation.
- Added branch protection runbook for `ShabalalaWATP/coeus`.
- Verified Sprint 2 gates: backend Ruff, mypy, pytest coverage, Bandit, pip-audit and Semgrep; frontend formatting, linting, typecheck, Vitest coverage, build, Playwright e2e and production dependency audit; Compose config and live browser auth smoke.

## 2026-07-04 Sprint 3

- Added local-first ACG, product and project workspace domain records plus a seed access repository.
- Added ACG, product access, project access, project workspace and access diagnostics services.
- Added backend routes for ACG administration, project workspaces, project slices and administrator product diagnostics.
- Added ACG audit events for group creation, group update, membership addition and membership removal.
- Added `/admin/acgs` and `/projects` frontend workspaces with ACG management, project plan, member, product and diagnostic views.
- Added Sprint 3 access-policy, API, client and UI tests.
- Added the Sprint 3 spec, ACG/project ADR and threat-model update.
- Verified local Sprint 3 gates: backend Ruff, mypy, pytest coverage, Bandit, pip-audit and Semgrep; frontend formatting, linting, typecheck, Vitest coverage, build, Playwright e2e and production dependency audit; Compose config.

## 2026-07-05 Sprint 4

- Added local-first ticket intake records for tickets, structured intake fields, chat messages, attachment metadata, agent runs and timeline entries.
- Added deterministic mock LLM and intake extraction services with completeness checks and prompt-injection safety flags.
- Added ticket and chat APIs for ticket listing, chat create/resume, intake editing, attachment metadata, submission and post-submission information.
- Added the `/app/requests` customer dashboard with ticket metrics, chat transcript, editable extracted intake, attachment metadata and timeline controls.
- Added Sprint 4 API, client and UI tests, including prompt-injection regressions.
- Added the Sprint 4 spec, local-first ticket intake ADR and threat-model document.
- Verified local Sprint 4 gates: backend Ruff, mypy, pytest coverage, Bandit, pip-audit and Semgrep; frontend Prettier, ESLint, TypeScript, Vitest coverage, build, Playwright e2e and package audit; Compose config.

## 2026-07-05 Sprint 5

- Added local-first Intelligence Store product, asset and metadata domain records.
- Added an in-memory store repository seeded from the existing ACG/project context.
- Added store services for product registration, access-filtered search, detail retrieval, controlled asset grants and metadata suggestions.
- Added `/api/v1/store` routes for search, create, detail, asset access and suggestions.
- Added frontend Store search, My Products, Product Detail and Upload Product routes.
- Added metadata-only upload controls with ACG selection, SHA-256 asset validation and synthetic metadata suggestions.
- Added Sprint 5 API, service, client and UI tests for ACG enforcement, count leakage, IDOR-style detail denial and asset access denial.
- Added the Sprint 5 spec, local-first Intelligence Store ADR and threat-model document.
- Verified local Sprint 5 gates: backend Ruff, mypy, pytest coverage, Bandit, pip-audit and Semgrep; frontend Prettier, ESLint, TypeScript, Vitest coverage, build, Playwright e2e and package audit; Compose config.

## 2026-07-05 Sprint 6

- Added the `packages/mock-product-generators` Python package for deterministic synthetic product generation.
- Added standard-library writers for mock PDF, DOCX, PNG, JPEG, GeoJSON, KML, CSV and JSON assets.
- Added a mock catalogue manifest with 190 default products, 410 asset descriptors, five ACG definitions and named access scenarios.
- Added `scripts/seed/seed_mock_products.py` with full and small smoke modes.
- Added generator tests for default counts, path-safe asset output, mock markers, deterministic IDs and CLI manifest creation.
- Added the Sprint 6 spec, standard-library generator ADR and mock product seeding threat model.
- Verified local Sprint 6 gates: backend Ruff, mypy, pytest coverage, Bandit, pip-audit and Semgrep; frontend Prettier, ESLint, TypeScript, Vitest coverage, build, Playwright e2e and package audit; seed smoke; file line limit; Compose config.
- Completed a Codex Security diff scan for the staged Sprint 6 change set with 0 findings and 9 of 9 worklist rows closed.

## 2026-07-05 Sprint 7

- Added the local-first RFI Search Agent service with requester-based access filtering before ranking.
- Added deterministic full-text, semantic and metadata ranking adapters behind the future PostgreSQL and pgvector boundary.
- Added product offers, search metrics, existing-product dissemination records, and accept or reject transitions.
- Added `/api/v1/rfi-search` endpoints for run, results, accept and reject.
- Added the request-dashboard Product Offers panel with run search, accept and rejection-reason controls.
- Added Sprint 7 API, service, client and UI tests for hybrid ranking, ACG and clearance filtering, count leakage, no-match routing, and offer accept or reject flows.
- Added the Sprint 7 spec, local-first RFI Search Agent ADR and threat-model document.
- Verified local Sprint 7 gates: backend Ruff, mypy, pytest coverage, Bandit, pip-audit and Semgrep; frontend Prettier, ESLint, TypeScript, Vitest coverage, build, Playwright e2e and package audit; file line limit; Compose config.
