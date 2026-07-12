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

The API initialises the PostgreSQL compatibility state table and the relational
Intelligence Store schema on startup. Alembic migrations for the same schema live
in `apps/api/src/coeus/db/migrations` for explicit database management. When
`COEUS_PERSISTENCE_PROVIDER=postgres` is active, Store products, assets, ACG
joins and semantic labels are mirrored into those relational tables.
