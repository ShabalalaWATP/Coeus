# Local Development Infrastructure

Sprint 1 local services are defined in the root `docker-compose.yml`.

Services:

- PostgreSQL with pgvector, exposed on `localhost:5432`.
- MinIO object storage, exposed on `localhost:9000` with console on `localhost:9001`.
- FastAPI service, exposed on `localhost:8000`.
- Vite web app, exposed on `localhost:5173`.

Run:

```powershell
pwsh ./scripts/dev.ps1
```

Use `pwsh ./scripts/dev.ps1 -Detached` to keep the stack running in the background.

