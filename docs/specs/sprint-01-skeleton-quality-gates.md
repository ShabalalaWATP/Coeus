# Sprint 1 Spec: Skeleton And Quality Gates

## Purpose

Establish the Coeus repository foundation before feature work starts.

## Scope

- Create the monorepo structure required by the implementation plan.
- Add a FastAPI API skeleton with liveness, readiness, request IDs, JSON logs, security headers and exception handling.
- Add a React/Vite TypeScript frontend shell with dark default theme, theme switch, logo slot, left navigation, command bar, profile menu and notification area.
- Add local development services for PostgreSQL with pgvector and object storage.
- Add backend and frontend CI with 95 percent line and branch coverage gates.
- Add initial ADRs and threat-model documentation.

## Non-goals

- Authentication, sessions, RBAC enforcement and seed users are Sprint 2.
- ACG data models and product access enforcement are Sprint 3 and Sprint 5.
- Real intelligence product ingestion is outside Sprint 1.
- GCP resources and Terraform are outside Sprint 1.

## Acceptance Criteria

- `uv run --directory apps/api pytest` passes with 95 percent minimum line and branch coverage.
- `pnpm --filter @coeus/web test` passes with 95 percent minimum line and branch coverage.
- The web app runs with `pnpm --filter @coeus/web dev`.
- The API runs with `uv run --directory apps/api uvicorn coeus.main:app`.
- `pwsh ./scripts/dev.ps1` starts the local Compose stack.
- No real secrets or operational data are committed.
