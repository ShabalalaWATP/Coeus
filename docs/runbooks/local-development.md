# Local Development Runbook

For the full local setup guide, including prerequisites and configuration, see
[../SETUP.md](../SETUP.md). This runbook is the short operational checklist.

## Recommended Local Mode

Run PostgreSQL in Docker, then run the API and web app as local processes.

```powershell
docker compose up -d postgres
uv run --project apps/api uvicorn coeus.main:app --host 127.0.0.1 --port 8001 --workers 1
corepack pnpm --filter @coeus/web dev
```

Open <http://127.0.0.1:5173>. The web app defaults to the API at
<http://127.0.0.1:8001>.

PostgreSQL must publish only on loopback. Recreate older containers after
pulling Compose changes, then confirm the rendered mapping uses
`127.0.0.1:5432:5432` rather than a wildcard host binding. The supplied Compose
credential is a public local-development value and its initial PostgreSQL user
is privileged; do not reuse either in a shared or hosted environment. A hosted
database must use a generated secret and a least-privilege application role
without `SUPERUSER`, `CREATEDB` or `CREATEROLE`.

Verify before development:

```powershell
docker compose config
docker compose up -d --force-recreate postgres
docker compose ps
Test-NetConnection 127.0.0.1 -Port 5432
```

From a second network namespace or LAN host, TCP/5432 must not be reachable.
`pwsh ./scripts/dev.ps1` performs the force-recreate and refuses to continue if
Docker still reports anything other than a `127.0.0.1` PostgreSQL binding. The
named PostgreSQL volume is preserved by this startup repair.

## Full Docker Stack

Use this when you want local container parity with PostgreSQL and the app
containers.

```powershell
pwsh ./scripts/dev.ps1
```

Add `-Detached` to keep the stack running in the background.
Compose waits for `/api/v1/health/ready` before starting the web service.

## Health Checks

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health/live
Invoke-RestMethod http://localhost:8000/api/v1/health/ready
```

For the recommended local-process API on port `8001`, use:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/v1/health/live
Invoke-RestMethod http://127.0.0.1:8001/api/v1/health/ready
```

## Seed Users

All seed accounts use mock usernames under `example.test` and the mock local
credential `CoeusLocal1!`. These accounts are for local development only.

The current account list is maintained in
[../SETUP.md#seed-accounts](../SETUP.md#seed-accounts).

## Reset Synthetic Data

Never remove object bytes separately from their PostgreSQL metadata. Stop the
host API, then run the provider-specific reset described in
[Setup](../SETUP.md#reset-local-synthetic-data-safely). The helper requires
`-ConfirmReset` and removes the database and the matching object store together.

## Local Quality Gates

```powershell
uv sync --project apps/api --all-groups
corepack pnpm install
corepack pnpm --filter @coeus/web format:check
corepack pnpm --filter @coeus/web lint
corepack pnpm --filter @coeus/web typecheck
corepack pnpm --filter @coeus/web test
uv run --directory apps/api ruff format --check src tests
uv run --directory apps/api ruff check src tests
uv run --directory apps/api mypy src
uv run --directory apps/api pytest
corepack pnpm contracts:check
corepack pnpm line-limit
corepack pnpm dead-code
```

Backend and frontend application code each maintain at least 95% line and branch
coverage. Hand-written files changed during normal work must stay within the
350-line limit. The OpenAPI contract check protects the committed API contract
from drift. The dead-code check uses Knip for the TypeScript workspace and
should stay clean before merging frontend changes.

Sprint 14B also requires the 16 sealed finding regression PoCs, event-loop
liveness checks, bounded collection maximum-plus-one tests, streaming download
memory checks and readiness connection-budget tests.
