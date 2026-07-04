# Local Development Runbook

## Start The Local Stack

```powershell
pwsh ./scripts/dev.ps1
```

Use detached mode:

```powershell
pwsh ./scripts/dev.ps1 -Detached
```

## Health Checks

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health/live
Invoke-RestMethod http://localhost:8000/api/v1/health/ready
```

## Frontend

```powershell
pnpm install
pnpm --filter @coeus/web dev
```

## Sprint 2 Seed Users

All Sprint 2 seed accounts use mock usernames under `example.test` and the mock local credential `CoeusLocal1!`. These accounts are for local development only.

- `admin@example.test`
- `user@example.test`
- `rfa.manager@example.test`
- `rfa.team@example.test`
- `collection.manager@example.test`
- `collection.team@example.test`
- `analyst@example.test`
- `qc.manager@example.test`
- `disabled@example.test`, blocked from login

## Backend

```powershell
uv sync --project apps/api --all-groups
uv run --directory apps/api uvicorn coeus.main:app --host 0.0.0.0 --port 8000
```

## Test Gates

```powershell
uv run --directory apps/api pytest
pnpm --filter @coeus/web test
```
