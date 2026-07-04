# Coeus API

FastAPI service for Coeus.

## Local Commands

```powershell
uv sync --all-groups
uv run pytest
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src
uv run uvicorn coeus.main:app --host 0.0.0.0 --port 8000
```

