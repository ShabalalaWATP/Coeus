# Setup Guide

Istari is local-first. The backend seeds all of its data into in-memory
repositories at start-up, so you can run the whole application with two processes
and no database. A full Docker stack is also provided for parity with deployment.

## Prerequisites

| Tool | Version | Purpose |
| --- | --- | --- |
| Python | 3.12+ | Backend runtime |
| [uv](https://docs.astral.sh/uv/) | latest | Python dependency and venv manager |
| Node.js | 22+ | Frontend runtime |
| pnpm | via `corepack` | Frontend package manager |
| Docker Desktop | latest | Optional: full local stack |

Enable pnpm through Corepack (it ships with Node) rather than installing it
globally:

```bash
corepack enable
```

## Install dependencies

From the repository root:

```bash
# Backend (creates apps/api/.venv and installs all groups)
uv sync --project apps/api --all-groups

# Frontend
corepack pnpm install
```

## Run the app (recommended: two processes)

This is the fastest way to develop and is how the app is verified. It needs no
database.

**Terminal 1: API on port 8001**

```bash
uv run --directory apps/api uvicorn coeus.main:app --host 127.0.0.1 --port 8001
```

**Terminal 2: web app on port 5173**

```bash
corepack pnpm --filter @coeus/web dev
```

Then open <http://127.0.0.1:5173>.

The web app defaults its API base URL to `http://127.0.0.1:8001`, and the API's
default CORS allow-list already includes `http://127.0.0.1:5173` and
`http://localhost:5173`, so the two line up with no extra configuration. To point
the web app at a different API, set `VITE_API_BASE_URL` before starting Vite.

## Run the app (full Docker stack)

For parity with the deployment topology (PostgreSQL with pgvector and MinIO):

```powershell
pwsh ./scripts/dev.ps1            # add -Detached to run in the background
```

This exposes:

- API: <http://localhost:8000/api/v1/health/live>
- Web: <http://localhost:5173>
- PostgreSQL: `localhost:5432`
- MinIO console: <http://localhost:9001>

## Seed accounts

All local seed accounts use mock `example.test` usernames and the mock local
credential `CoeusLocal1!`. They exist only in `local` and `test` environments.

| Username | Role | Lands on |
| --- | --- | --- |
| `admin@example.test` | Administrator | `/admin/overview` |
| `user@example.test` | User (Customer) | `/app/requests` |
| `rfa.manager@example.test` | RFA Manager | `/rfa/queue` |
| `rfa.team@example.test` | RFA Team Member | `/rfa/products` |
| `collection.manager@example.test` | Collection Manager | `/collection/queue` |
| `collection.team@example.test` | Collection Team Member | `/collection/products` |
| `analyst@example.test` | Intelligence Analyst | `/analyst/workbench` |
| `qc.manager@example.test` | Quality Control Manager | `/qc/queue` |
| `disabled@example.test` | (disabled) | Blocked from login |

To exercise the full workflow, sign in as the customer to raise a request, then
sign in as the RFA manager, analyst and QC manager in turn to move it through the
pipeline. See the [User Guide](USER_GUIDE.md).

## Running the checks

The same gates run in CI. From the repository root:

```bash
# Frontend: format, lint, types, tests with coverage
corepack pnpm --filter @coeus/web format:check
corepack pnpm --filter @coeus/web lint
corepack pnpm --filter @coeus/web typecheck
corepack pnpm --filter @coeus/web test

# Backend: format, lint, types, tests with coverage
uv run --directory apps/api ruff format --check src tests
uv run --directory apps/api ruff check src tests
uv run --directory apps/api mypy src
uv run --directory apps/api pytest

# Repository: hand-written files must stay within the 350-line limit
corepack pnpm line-limit
```

Backend and frontend application code each hold at least 95% line and branch
coverage. Do not lower the coverage gates.

## Configuration and secrets

- Configuration is read from environment variables prefixed `COEUS_` (and an
  optional `.env`). See `apps/api/src/coeus/core/config.py`.
- Never commit real secrets. `.env` is gitignored; `.env.example` ships with
  blank secret fields.
- Outside `local`/`test`, start-up fails closed if session/CSRF secrets are too
  short, if secure cookies are off in staging/prod, or if dev seed users are
  enabled without overriding the default seed credential. This is by design: it
  stops a known default password ever reaching a deployed environment.

## Troubleshooting

- **Login returns "Authentication failed" right after starting the API.** The
  first request can race the server start; wait a second and retry.
- **CORS or preflight errors in the browser.** Make sure the web origin matches
  the API's allow-list. If you run the web app on a non-default port, set the
  API's `COEUS_ALLOWED_CORS_ORIGINS` to include that origin.
- **`pnpm` not found.** Use `corepack pnpm ...`; pnpm is provided by Corepack and
  may not be on the global PATH.
- **Stale session after restarting the API.** The in-memory store resets on
  restart; sign in again to get a fresh session.
