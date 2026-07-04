# Coeus

Coeus is a secure, role-based intelligence tasking and intelligence product orchestration platform.

This repository is being implemented from `coeus_spec_driven_implementation_plan.md`. The current baseline covers Sprint 1: monorepo skeleton, FastAPI foundation, React/Vite app shell, local development services, CI, initial specs, ADRs, and threat model.

## Repository Safety

`ShabalalaWATP/coeus` is intended to be public. Do not commit real intelligence products, real operational examples, private URLs, credentials, classified strings, internal schemas, browser screenshots, or personal account details. Seed data and fixtures must be synthetic and clearly labelled as mock.

## Local Tooling

- Python 3.12 or later
- `uv`
- Node.js 22 or later
- `pnpm`
- Docker Desktop, for the local database and object store

## Commands

```powershell
pnpm install
uv sync --project apps/api --all-groups
pnpm --filter @coeus/web test
uv run --directory apps/api pytest
pwsh ./scripts/dev.ps1
```

The local stack exposes:

- API: `http://localhost:8000/api/v1/health/live`
- Web: `http://localhost:5173`
- PostgreSQL: `localhost:5432`
- MinIO console: `http://localhost:9001`

## GitHub

The implementation plan targets `ShabalalaWATP/coeus`. This local repository has `origin` configured for that URL, but the first push should be a deliberate step once the Sprint 1 baseline has passed checks.
