# Coeus API

FastAPI service for Coeus.

## Local commands

Run these commands from the repository root so the API loads the root `.env`
and agrees with the documented frontend origin:

```powershell
docker compose up -d postgres
uv sync --project apps/api --all-groups
$env:COEUS_TEST_DATABASE_URL = "postgresql+psycopg://coeus:coeus-local@127.0.0.1:5432/coeus"
uv run --directory apps/api pytest --cov-report=json:coverage.json
uv run --project apps/api python scripts/check_backend_coverage.py apps/api/coverage.json
uv run --directory apps/api ruff format --check src tests
uv run --directory apps/api ruff check src tests
uv run --directory apps/api mypy src
uv run --project apps/api uvicorn coeus.main:app --host 127.0.0.1 --port 8001 --workers 1
```

The supported local configuration includes published synthetic seed accounts,
so keep it loopback-bound. The remaining process-local repositories require
exactly one API process. Do not
increase the worker count or run multiple API containers until ADR 0019's
distributed-state migration gates pass.

## Real PostgreSQL tests

The full coverage command above and the focused migration/concurrency harness
create and drop uniquely named databases.
Point it only at a disposable PostgreSQL server where the configured user may
create databases:

```powershell
$env:COEUS_TEST_DATABASE_URL = "postgresql+psycopg://coeus:coeus-local@127.0.0.1:5432/coeus"
uv run --directory apps/api pytest -m postgres --no-cov tests/postgres
```
