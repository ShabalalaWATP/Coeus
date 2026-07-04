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
