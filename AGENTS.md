# Coeus Repository Instructions

These instructions are specific to the Coeus repository and sit below Alex Orr's global Codex instructions.

## Project Shape

- Coeus is a public-repository-safe, secure intelligence tasking and product orchestration platform.
- Treat all data in this repository as synthetic. Do not commit real intelligence content, internal URLs, credentials, screenshots, classified strings, private schemas, or operational examples.
- Build phase by phase from `coeus_spec_driven_implementation_plan.md`. Do not jump to later sprint features until the current sprint's tests and acceptance criteria pass.
- Use UK English in documentation, comments, PR descriptions, and user-facing text.

## Stack Defaults

- Backend: Python 3.12 or later, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, PostgreSQL with pgvector.
- Frontend: React, Vite, TypeScript, React Router, TanStack Query, React Hook Form, Zod, Vitest, React Testing Library, Playwright.
- Local development should run without Google Cloud access.

## Quality Gates

- Backend and frontend application code must each maintain at least 95 percent line and branch coverage.
- Do not lower coverage gates to make checks pass.
- Hand-written files changed during normal work have a hard maximum of 350 lines. Split by responsibility before exceeding this limit. Generated files, lockfiles, migrations and the root implementation plan are exceptions only when clearly justified.
- Keep route handlers thin. Put business logic in services, domain modules, repositories, or integrations.
- Keep React components small and move access logic into `lib/permissions` or equivalent helpers.
- Security-sensitive changes must update `docs/threat-model/`.
- Material design or architecture decisions must have an ADR in `docs/adr/`.
- Every feature starts with a Markdown spec in `docs/specs/`.

## Common Commands

- Root install: `pnpm install`
- File line limit: `pnpm line-limit`
- Backend sync: `uv sync --project apps/api --all-groups`
- Backend checks: `uv run --directory apps/api pytest`
- Frontend checks: `pnpm --filter @coeus/web test`
- Local stack: `pwsh ./scripts/dev.ps1`
