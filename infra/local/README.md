# Local Development Infrastructure

The app is intended to run locally for development and demos. The fastest path is
the two-process setup in `docs/SETUP.md`; the root `docker-compose.yml` is
available when you want local PostgreSQL, MinIO and container parity.

Services:

- PostgreSQL with pgvector, exposed on `127.0.0.1:5432`.
- MinIO parity scaffolding, exposed on `localhost:9000` with console on
  `localhost:9001`; current uploads do not use it.
- FastAPI service, exposed on `localhost:8000`.
- Vite web app, exposed on `localhost:5173`.

Run:

```powershell
pwsh ./scripts/dev.ps1
```

Use `pwsh ./scripts/dev.ps1 -Detached` to keep the stack running in the background.

The API initialises its supported PostgreSQL schema on startup. Versioned ticket
aggregates, workflow outbox records, audit events, draft audiences, Store
products and both search indexes use relational tables. The resource-lease
schema exists for hosted adapters, but supported local admission is
process-local. Remaining bounded namespaces use the `coeus_state` compatibility
table. Alembic migrations for the same schema live in
`apps/api/src/coeus/db/migrations` for explicit database management and
coordinated recovery evidence.
