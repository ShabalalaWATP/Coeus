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

## 2026-07-05 Sprint 8

- Added local-first RFA and CM capability agents for deterministic route assessment.
- Added ticket-level RFA reviews, CM reviews, route recommendations, clarification requests, manager decisions and project-plan updates.
- Added `/api/v1/routing` endpoints for RFA queue, CM queue, route checks, approval, rejection, clarification and statistics.
- Added RFA-first routing, CM fallback and neither-capable clarification behaviour.
- Added human approval and manager override audit coverage before analyst assignment.
- Added real `/rfa/queue` and `/collection/queue` frontend pages with manager actions and route statistics.
- Added Sprint 8 API, service, client and UI tests for capability routing, fallback, clarification, approval and override flows.
- Added the Sprint 8 spec, local-first routing agents ADR and threat-model document.
- Verified local Sprint 8 gates: backend Ruff, mypy, pytest coverage, Bandit, pip-audit and Semgrep; frontend Prettier, ESLint, TypeScript, Vitest coverage, build, Playwright e2e and package audit; file line limit; Compose config.

## 2026-07-05 Sprint 9

- Added ticket-level analyst assignments, work packages, notes, linked products and draft product versions.
- Added `AnalystWorkflowService` for manager assignment, assigned-only task visibility, note creation, product linking, work-package completion, draft versioning and QC submission.
- Added `/api/v1/analyst` endpoints for candidates, assigned tasks, assignment, notes, product links, work packages, drafts and submit-to-QC.
- Added `ANALYST_IN_PROGRESS` and `QC_REVIEW` state transitions.
- Added a real `/analyst/workbench` and `/analyst/tasks/:taskId` frontend with checklist, notes, product search and draft controls.
- Added Sprint 9 API, service, client and UI tests for assignment, visibility, product-link access, draft versioning and QC submission flows.
- Added the Sprint 9 spec, local-first analyst workflow ADR and threat-model document.
- Verified local Sprint 9 gates: backend Ruff, mypy, pytest coverage, Bandit, pip-audit and Semgrep; frontend Prettier, ESLint, TypeScript, Vitest coverage, build, Playwright e2e and package audit; file line limit; Compose config.

## 2026-07-05 Sprint 10

- Added ticket-level QC decisions, checklist records, product index records and feedback request records.
- Added `QualityControlService` plus release-check, auto-ingestion, indexing, dissemination and feedback-request services.
- Added `REWORK_REQUIRED` and `DISSEMINATION_READY` states for QC rejection, analyst rework and approved dissemination.
- Added `/api/v1/qc` endpoints for queue, product detail, approval and rejection.
- Added automatic published Store product creation from approved analyst drafts with project and QC-confirmed ACG assignment.
- Added requester dissemination only after Store visibility validation, plus local queued and indexed records.
- Added a real `/qc/queue` and `/qc/products/:productId` frontend with product preview, checklist, metadata checks, approve and return-to-analyst actions.
- Added Sprint 10 API, service, client and UI tests for approval, rejection, separation of duties, auto-ingestion, dissemination, feedback requests and search visibility.
- Added the Sprint 10 spec, local-first QC ingestion ADR and QC dissemination threat model.
- Verified local Sprint 10 gates: backend Ruff, mypy, pytest coverage, Bandit, pip-audit and Semgrep; frontend Prettier, ESLint, TypeScript, Vitest coverage, build, Playwright e2e and package audit; file line limit; Compose config.

## 2026-07-05 Sprint 11

- Added ticket-level feedback submissions and submitted feedback-request state.
- Added `FeedbackAnalyticsService` for one-time requester feedback submission, dashboard scoping, product reuse aggregation and metrics.
- Added deterministic `TrendsAnalysisAgent` insights for request region, product reuse and requester satisfaction.
- Added `/api/v1/feedback` endpoints for request listing and submission.
- Added `/api/v1/analytics/admin`, `/api/v1/analytics/rfa` and `/api/v1/analytics/collection` dashboards.
- Added a customer feedback panel on `/app/requests`.
- Added admin, RFA and collection analytics dashboard routes.
- Added Sprint 11 API, service, client and UI tests for feedback submission, duplicate prevention, dashboard scoping, reuse analytics and trend rendering.
- Added the Sprint 11 spec, local-first feedback analytics ADR and feedback analytics threat model.
- Verified local Sprint 11 gates: backend Ruff, mypy, pytest coverage, Bandit, pip-audit and Semgrep; frontend Prettier, ESLint, TypeScript, Vitest coverage, build, Playwright e2e, package audit and pnpm supply-chain policy; file line limit; Compose config.

## 2026-07-05 Sprint 12

- Added a GCP dev deployment baseline with Terraform modules for services, IAM,
  Workload Identity Federation, Artifact Registry, Cloud Run, Cloud SQL, Cloud
  Storage, Secret Manager and Pub/Sub.
- Added a manual-first `Deploy Dev` GitHub Actions workflow that builds API and
  web images, pushes them to Artifact Registry and deploys to Cloud Run through
  GitHub OIDC.
- Added GCP, GCS, Pub/Sub and Gemma Vertex runtime settings without importing
  cloud SDKs into domain services.
- Added a production web container image for Cloud Run.
- Added the Sprint 12 spec, GCP deployment ADR, threat model and deployment
  runbook.
- Verified local Sprint 12 gates: backend Ruff, mypy, pytest coverage, Bandit,
  pip-audit and Semgrep; frontend Prettier, ESLint, TypeScript, Vitest
  coverage, build, Playwright e2e and package audit; Terraform fmt and
  validate; file line limit; Compose config.

## 2026-07-05 Sprint 13

- Hardened CodeQL with extended and security-and-quality query suites.
- Hardened Semgrep with `auto` and OWASP Top 10 rules across app source,
  Dockerfiles, Terraform and GitHub workflows.
- Added Gitleaks committed-history scanning and CycloneDX SBOM generation.
- Added Trivy scanning for API and web container images.
- Added Checkov Terraform scanning with SARIF upload.
- Added a ZAP baseline workflow against a local CI-hosted web target.
- Extended Dependabot coverage to Docker and Terraform.
- Hardened Terraform with a KMS module, customer-managed encryption for
  Artifact Registry and Pub/Sub, Cloud SQL audit logging, disabled public SQL
  IPv4, narrower GitHub OIDC trust and GCS access logging.
- Added a prompt-injection regression suite for jailbreak, system prompt,
  RBAC bypass, admin escalation, tool abuse and fabricated product attempts.
- Added the Sprint 13 spec, security gates ADR, security-hardening threat model
  and air-gapped deployment runbook.
- Verified local Sprint 13 gates: backend Ruff, mypy, pytest coverage, Bandit
  and pip-audit; frontend Prettier, ESLint, TypeScript, Vitest coverage, build,
  Playwright e2e and production dependency audit; Terraform fmt, init and
  validate; Checkov, Semgrep, Gitleaks, file line limit and Compose config.

## 2026-07-06 Frontend design and role-view polish

- Reworked the frontend design system for a dark, operational look: expanded
  colour tokens with graphite surfaces and cyan, teal, green, amber and red
  accents, a monospace accent face for references and tokens, grouped
  navigation with section labels, a sticky blurred command bar with a
  Ctrl+K shortcut, subtle hover and focus motion, and a technical grid
  backdrop on the auth pages. All animation respects
  `prefers-reduced-motion` and the light theme remains supported.
- Completed the manager-to-analyst workflow in the UI: after route approval a
  ticket now stays in the routing queue with an assign-analyst panel backed by
  the existing `/analyst/candidates` and `/analyst/tasks/{id}/assign`
  endpoints, so tickets no longer dead-end in `ANALYST_ASSIGNMENT`.
- Gated ACG create, update and add-member forms behind `acg:create`,
  `acg:update` and `acg:assign_user` permissions so view-only roles no longer
  see actions they cannot use.
- Added shared `LoadingState`, `ErrorState`, `EmptyState` and `StatusPill`
  components with styles for the previously unstyled `request-row` and
  `status-pill` classes, and wired loading, error, empty and success states
  into the store, projects, analytics, audit, requests, routing, analyst, QC
  and ACG pages.
- Preserved product back-navigation context from team workspaces and project
  pages, and relabelled the controlled asset grant with token expiry.
- Verified all eight role views end to end in the browser, including the full
  intake, RFI search, routing, assignment, analyst production and QC
  dissemination pipeline, auth negative states and responsive layouts at
  1440x900, 1280x720, 768x1024 and 390x844.

## 2026-07-06 Istari rebrand, splash login and access requests

- Rebranded the product from Coeus to Istari across the web UI, page
  metadata, favicon and the FastAPI docs title, using the supplied logo with
  resized 64px and 256px assets. Internal package, module and infrastructure
  identifiers keep the `coeus` working name.
- Rebuilt the login page as a splash introduction: glowing, gently floating
  logo, "Task. Assess. Deliver." tagline, a short pitch, three capability
  points and an access card that switches between sign in and request
  access. Animations remain CSS-only and respect `prefers-reduced-motion`.
- Added a self-service registration flow: public `POST /auth/register` with
  Argon2 hashing at submission, generic anti-enumeration responses, a
  pending-request cap with `429` throttling, and admin review endpoints
  gated by `user:create` plus CSRF. Approval creates an active `User`
  account at clearance level 1; decisions are audit logged.
- Added an Access Requests panel to the admin overview for approving or
  rejecting requests with a recorded reason, plus a spec and threat model
  for the feature.
- Verified in the browser: request submission, admin approval, first login
  of the approved account, rejection with generic sign-in failure, splash
  responsiveness at 390, 768 and 1440 widths and the light theme.
