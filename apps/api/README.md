# Coeus API

FastAPI service for Coeus.

## Local Commands

```powershell
uv sync --all-groups
uv run pytest --cov-report=json:coverage.json
uv run python ../../scripts/check_backend_coverage.py coverage.json
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src
uv run uvicorn coeus.main:app --host 0.0.0.0 --port 8000 --workers 1
```

The current local-first repositories require exactly one API process. Do not
increase the worker count or run multiple API containers until ADR 0019's
distributed-state migration gates pass.

## Real PostgreSQL Tests

The migration and concurrency harness creates and drops uniquely named databases.
Point it only at a disposable PostgreSQL server where the configured user may
create databases:

```powershell
$env:COEUS_TEST_DATABASE_URL = "postgresql+psycopg://coeus:coeus-local@127.0.0.1:5432/coeus"
uv run pytest -m postgres --no-cov tests/postgres
```
