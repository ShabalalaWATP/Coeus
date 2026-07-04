# ADR 0001: Monorepo With FastAPI And Vite

## Status

Accepted.

## Context

The implementation plan requires a monorepo with a Python FastAPI backend and React/Vite frontend. Sprint 1 must create a quality-gated skeleton before feature work begins.

## Decision

Use:

- `apps/api` for the FastAPI service.
- `apps/web` for the React/Vite frontend.
- `packages/contracts` for generated API contracts.
- `packages/test-fixtures` for safe fixtures.
- `packages/mock-product-generators` for later synthetic product generation.

Python dependencies are managed with `uv`. Frontend dependencies are managed with `pnpm`.

## Consequences

- Backend and frontend checks can run independently in CI.
- Shared generated artefacts have a clear home outside business logic.
- The repository can evolve into separate deployable services without splitting source control early.

