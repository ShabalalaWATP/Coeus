# Coeus Master Implementation Plan

The authoritative project implementation plan is `coeus_spec_driven_implementation_plan.md` at the repository root.

This document tracks delivery state as implementation progresses.

## Current Stage

Sprint 4: Ticket and Chatbot Intake.

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
