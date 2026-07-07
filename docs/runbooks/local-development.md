# Local Development Runbook

For the full local setup guide, including prerequisites and configuration, see
[../SETUP.md](../SETUP.md). This runbook is the short operational checklist.

## Recommended Local Mode

Run PostgreSQL in Docker, then run the API and web app as local processes.

```powershell
docker compose up -d postgres
uv run --directory apps/api uvicorn coeus.main:app --host 127.0.0.1 --port 8001
corepack pnpm --filter @coeus/web dev
```

Open <http://127.0.0.1:5173>. The web app defaults to the API at
<http://127.0.0.1:8001>.

## Full Docker Stack

Use this when you want local container parity with PostgreSQL and the app
containers.

```powershell
pwsh ./scripts/dev.ps1
```

Add `-Detached` to keep the stack running in the background.

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
corepack pnpm line-limit
```

Backend and frontend application code each maintain at least 95% line and branch
coverage. Hand-written files changed during normal work must stay within the
350-line limit.
