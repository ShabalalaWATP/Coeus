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
