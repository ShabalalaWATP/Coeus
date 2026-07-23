# Coeus Contracts

Shared API contracts live here, outside backend and frontend business logic.

- `openapi.json` is generated from the FastAPI application.
- Run `pnpm contracts:generate` after API route or schema changes.
- Run `pnpm contracts:check` to reject generated-contract drift and breaking
  changes against `origin/main`. Fetch or update that ref before running the
  compatibility check locally.
