# Coeus

Coeus is a secure, role-based intelligence tasking and intelligence product orchestration platform.

This repository is being implemented from `coeus_spec_driven_implementation_plan.md`. The current baseline covers Sprint 1 through Sprint 7 foundations: monorepo skeleton, FastAPI foundation, React/Vite app shell, local development services, CI, authentication, sessions, RBAC, ACG and project workspace access controls, ticket intake, mock chatbot extraction, customer request dashboard, Intelligence Store metadata search and controlled asset access, deterministic mock product seeding, RFI Search Agent product offers, specs, ADRs and threat models.

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
pnpm --filter @coeus/web test:e2e
python scripts/seed/seed_mock_products.py --small --output-dir .local/mock-products-smoke
pwsh ./scripts/dev.ps1
```

The local stack exposes:

- API: `http://localhost:8000/api/v1/health/live`
- Web: `http://localhost:5173`
- PostgreSQL: `localhost:5432`
- MinIO console: `http://localhost:9001`

Local seed users use mock `example.test` usernames and the mock local credential `CoeusLocal1!`. See `docs/specs/sprint-02-auth-rbac-sessions.md`.

Mock product seed data is generated locally and is not committed. The full
catalogue creates 190 products and 410 assets under `.local/mock-products` by
default; every product and asset is synthetic and marked `MOCK DATA ONLY`.

## GitHub

The implementation plan targets `ShabalalaWATP/coeus`. Work lands through protected-main pull requests with required CI/security checks.
