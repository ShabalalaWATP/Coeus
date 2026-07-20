# Setup Guide

Istari is currently designed to run locally on a developer machine with a local
PostgreSQL database. This keeps local development aligned with the future
production direction on Google Cloud SQL for PostgreSQL while requiring no GCP
account or hosted service. Uploaded asset bytes are stored in a local object
directory for now.

## Prerequisites

| Tool                             | Version | Purpose                                      |
| -------------------------------- | ------- | -------------------------------------------- |
| Python                           | 3.12+   | Backend runtime                              |
| [uv](https://docs.astral.sh/uv/) | latest  | Python dependency and venv manager           |
| Node.js                          | 22.12+  | Frontend runtime required by locked Vite 7   |
| pnpm                             | 11.11.0 | Frontend package manager                     |
| Docker Desktop                   | latest  | Local PostgreSQL and optional full app stack |

When Corepack is available, enable the repository-pinned pnpm version:

```bash
corepack enable
corepack prepare pnpm@11.11.0 --activate
```

Some newer Node distributions do not bundle Corepack. In that case, install the
exact pinned pnpm version from npm, then verify both tools:

```bash
npm install --global --ignore-scripts pnpm@11.11.0
node --version
pnpm --version
```

Node must report `v22.12.0` or newer and pnpm must report `11.11.0`.

## Install dependencies

From the repository root:

```bash
# Backend (creates apps/api/.venv and installs all groups)
uv sync --project apps/api --all-groups

# Frontend
corepack pnpm install
```

Create a root `.env` from the safe example values. The file is gitignored and
keeps local persistence, object storage and optional integration settings out of
committed source. Use the `uv run --project apps/api` runtime command below: it
keeps the working directory at the repository root, so Pydantic loads this file
and relative `.local-data` paths resolve where documented.

```bash
cp .env.example .env
```

### JIOC routing configuration upgrade

Coeus's supported synthetic local/test runtime ships the evaluated JIOC release
in `active` mode, so eligible new tasking is automatically classified as CM or
RFA. Unsafe or ambiguous evidence still refers the request to human JIOC review.
Existing `.env` files override this baseline: set
`COEUS_JIOC_AGENT_ROUTING_ENABLED=active` and pin the current identifier in
`COEUS_JIOC_ROUTING_APPROVED_RELEASES`. Hosted deployments must explicitly set
the mode and release approval; keep them disabled until production evidence is
approved. `disabled` is the restart/redeployment kill switch; `shadow` records
evidence only. Legacy `true` requires an explicit release approval.

Hosted environments must also set a random `COEUS_METRICS_BEARER_TOKEN` of at
least 32 characters. Monitoring sends it in the `Authorization: Bearer` header;
the metrics route remains unauthenticated only for local and test use when no
token is configured. Keep hosted metrics on private monitoring ingress as well.

## Run the app (recommended local development)

This is the supported default for current development and demos. It runs
PostgreSQL in Docker, then runs the API and web app as normal local processes.
The app stores persisted state in PostgreSQL and uploaded asset bytes under
`.local-data/objects`.

**Terminal 1: PostgreSQL**

```bash
docker compose up -d postgres
```

**Terminal 2: API on port 8001**

```bash
uv run --project apps/api uvicorn coeus.main:app --host 127.0.0.1 --port 8001 --workers 1
```

Run one API process only. The current local repositories are deliberately
single-writer; ADR 0019 defines the future scale-out prerequisites.

**Terminal 3: web app on port 5173**

```bash
corepack pnpm --filter @coeus/web dev
```

Then open <http://127.0.0.1:5173>.

The web app defaults its API base URL to `http://127.0.0.1:8001`, and the API's
default CORS allow-list already includes `http://127.0.0.1:5173` and
`http://localhost:5173`, so the two line up with no extra configuration. To point
the web app at a different API, set `VITE_API_BASE_URL` before starting Vite.

## Run the app (full Docker stack)

For local container parity, Docker starts PostgreSQL, MinIO and the app
containers. The API stores app state in PostgreSQL and keeps uploaded asset bytes
on a named local Docker volume. Compose supplies explicit local settings; the
root `.env` is not an application `env_file` for these containers.

```powershell
pwsh ./scripts/dev.ps1            # add -Detached to run in the background
```

This exposes:

- API: <http://localhost:8000/api/v1/health/live>
- Web: <http://localhost:5173>
- PostgreSQL: `127.0.0.1:5432`
- MinIO console: <http://localhost:9001>

Current uploads use the app's local object-storage adapter rather than MinIO.
MinIO remains in the stack as future object-storage parity scaffolding.
Compose waits for the API readiness endpoint before starting the web service.

## Seed accounts

All local seed accounts use mock `example.test` usernames and the mock local
credential `CoeusLocal1!`. They exist only in `local` and `test` environments.

| Username                          | Synthetic display name | Role                       | Lands on               |
| --------------------------------- | ---------------------- | -------------------------- | ---------------------- |
| `admin@example.test`              | Andy Robertson         | Administrator              | `/admin/overview`      |
| `user@example.test`               | John McGinn            | Customer                   | `/app/requests`        |
| `colleague@example.test`          | Billy Gilmour          | Customer                   | `/app/requests`        |
| `jioc.team@example.test`          | Scott McTominay        | JIOC Team Member           | `/jioc/queue`          |
| `rfa.manager@example.test`        | Kieran Tierney         | RFA Manager                | `/rfa/queue`           |
| `rfa.team@example.test`           | Ryan Christie          | RFA Team Member            | `/rfa/products`        |
| `collection.manager@example.test` | Grant Hanley           | CM Manager                 | `/collection/queue`    |
| `collection.team@example.test`    | Kenny McLean           | CM Team Member             | `/collection/products` |
| `store.manager@example.test`      | Craig Gordon           | Intelligence Store Manager | `/store`               |
| `analyst@example.test`            | Lewis Ferguson         | Analyst                    | `/analyst/workbench`   |
| `analyst.2@example.test`          | Nathan Patterson       | Analyst                    | `/analyst/workbench`   |
| `analyst.3@example.test`          | Ben Doak               | Analyst                    | `/analyst/workbench`   |
| `analyst.4@example.test`          | Che Adams              | Analyst                    | `/analyst/workbench`   |
| `qc.manager@example.test`         | Angus Gunn             | Quality Control Manager    | `/qc/queue`            |
| `disabled@example.test`           | James Forrest          | Customer (disabled)        | Blocked from login     |

The display names borrow from Scottish footballers, but every local profile is
a fictional exercise persona and does not describe the real person.

Four organisational teams are also seeded for the My Team page (`/teams`): the
RFA Assessment Team (RFA manager plus the analysts), the Collection Management
Team, the JIOC Routing Cell and the Quality Control Cell. Team members get an
editable profile and a shared availability calendar.

### Local demo dataset

On a fresh local run the app also loads a rich demo dataset so no queue starts
empty: ~43 Intelligence Store products across the themed need-to-know groups
and every canonical product type (standardised reports, intelligence
summaries, satellite imagery, GeoJSON geographic overlays, database extracts,
SIGINT datasets, multi-asset bundles and fused outputs) with type-appropriate
assets, metadata and tags; a ticket in every workflow state (populating the
customer, JIOC, team, analyst and QC queues); delivered tickets with feedback
that feed the analytics dashboards; and team calendar entries. It is committed
as deterministic seed code, so a `git pull` brings it with the repository and
it repopulates any fresh database automatically. It is auto-on for
`environment=local` only; override with `COEUS_SEED_DEMO_CONTENT=true|false`.
The catalogue refreshes on restart even on an existing database; demo tickets
and calendars seed only on a fresh dataset. See
[Local Demo Dataset](specs/local-demo-dataset.md).

### Reset local synthetic data safely

PostgreSQL metadata and object bytes form one consistency unit. Never delete
`.local-data/objects`, the Docker object volume or selected `coeus_state` rows
on their own. Missing bytes for persisted products can otherwise be replaced by
synthetic placeholders on restart.

Stop the local-process API first, then choose the mode you actually use. Both
commands require the explicit destructive confirmation flag and remove the
PostgreSQL volume and matching object storage together:

```powershell
# PostgreSQL in Docker, API/web as host processes
pwsh ./scripts/reset-local.ps1 -Mode LocalProcesses -ConfirmReset

# Entire app in Docker Compose
pwsh ./scripts/reset-local.ps1 -Mode FullDocker -ConfirmReset
```

Restart through the normal setup command. The deterministic seed users and demo
dataset will be recreated. These reset commands are for synthetic local data
only, not backup or production recovery.

To exercise the full workflow, sign in as the customer to raise a request, then
sign in as the JIOC team member to route it, and as the team manager, analyst
and QC manager in turn to move it through the pipeline. See the
[User Guide](USER_GUIDE.md).

## Local multi-user evaluation

Local accounts can request access, then administrators can manage roles,
clearance, status and credentials from **Users**. Team managers manage roster
membership separately, and ACG administrators grant need-to-know membership.
See [Local Multi-User Operations](runbooks/local-multi-user-operations.md) for the
complete lifecycle and its boundaries. This is a single-writer local evaluation
model, not a supported production identity or organisation-wide hosting setup.

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
uv run --directory apps/api pytest --cov-report=json:coverage.json
uv run --project apps/api python scripts/check_backend_coverage.py apps/api/coverage.json

# API contract: fail if packages/contracts/openapi.json is stale
corepack pnpm contracts:check

# Repository: hand-written files must stay within the 350-line limit and dead code checks
corepack pnpm line-limit
corepack pnpm dead-code
```

Backend and frontend application code each hold at least 95% line and branch
coverage. Do not lower the coverage gates.

## Configuration and secrets

- Configuration is read from environment variables prefixed `COEUS_` (and an
  optional `.env`). See `apps/api/src/coeus/core/config.py`.
- Never commit real secrets. `.env` is gitignored; `.env.example` ships with
  blank secret fields.
- Leave `COEUS_ENVIRONMENT=local`, `COEUS_OBJECT_STORAGE_PROVIDER=local`,
  `COEUS_EMAIL_PROVIDER=outbox` and `COEUS_PUBSUB_ENABLED=false` for normal
  local use.
- `COEUS_PERSISTENCE_PROVIDER=postgres` writes application state to the local
  PostgreSQL service. The startup path creates the compatibility `coeus_state`
  JSONB table plus relational Intelligence Store tables for products, assets,
  ACG joins, semantic labels, full-text search and pgvector-ready embeddings.
  Store product writes are mirrored into those relational tables, so local
  development follows the same PostgreSQL shape expected for Cloud SQL later.
  `memory` is only for isolated tests and throwaway demos; `file` is retained as
  an explicit fallback, not the product target. `COEUS_PERSISTENCE_PATH` is
  ignored unless that fallback is deliberately enabled.
- Alembic migration files live under `apps/api/src/coeus/db/migrations`; apply
  them from the repository root with
  `uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head` when
  managing a persistent database explicitly. The configuration resolves paths
  from its own directory, while application settings still load the root
  `.env`.
- Store uploads write real file bytes under `COEUS_LOCAL_OBJECT_STORAGE_PATH`.
  Downloads require an authenticated session plus the signed, expiring token
  returned by the asset-access endpoint.
- To use a real LLM from your machine without deploying, an administrator can
  paste an API key on `/admin/overview`, test the connection, and explicitly
  activate the provider. Gemini API is the primary provider; OpenAI, GCP
  Vertex AI (express-mode key) and AWS Bedrock (long-term API key) are
  optional alternatives. Admin-entered keys are never returned to the browser;
  they are encrypted in isolated provider namespaces and restored after an API
  restart. The active provider and every selected text or voice model are also
  restored. Saving a key does not switch the provider: activation is a
  separate, warned action that applies to every user immediately and notifies
  all administrators. Leave everything unset for offline mock behaviour.
- Local mode creates `.local-data/secrets/configuration.key` when needed. Keep
  that ignored file private and back it up separately from PostgreSQL. Docker
  stores it in the API local-data volume. Hosted deployments must set
  `COEUS_CONFIGURATION_ENCRYPTION_KEY` from a secret manager; losing or changing
  it makes saved admin credentials unreadable. Environment-managed provider
  keys remain authoritative. Hosted Intake Planner egress is unavailable until
  ticket classification is enforceable. Hosted Search Planner and Routing Critic
  egress stays off until its flag is true; the selected provider and `synthetic`
  class must also appear in the advisory approval lists in `.env.example`.
- To send real emails locally, set `COEUS_EMAIL_PROVIDER=smtp`,
  `COEUS_SMTP_HOST`, `COEUS_SMTP_FROM` and any required username/password. The
  default `outbox` provider records and audits emails without sending them.
- Store search is hybrid: Postgres full text plus a pgvector semantic leg. The
  embedding provider is selected by `COEUS_EMBEDDING_PROVIDER`, which defaults to
  `mock` (deterministic, offline, no dependencies). For a real offline model set
  `COEUS_EMBEDDING_PROVIDER=local` and install the optional extra:

  ```powershell
  uv sync --project apps/api --extra embeddings
  ```

  The model (`BAAI/bge-small-en-v1.5`, 384 dimensions) loads from
  `COEUS_EMBEDDING_MODEL_PATH` (default `.local-data/embedding-models`); download
  it there in advance for a fully offline machine. `gemini_api` uses the
  configured Gemini key. The provider setting is authoritative: a key present in
  the environment never switches the provider on by itself. If the provider is
  unavailable at query time, search degrades to the lexical leg alone rather than
  failing.

- Embeddings are written when products are created, updated or ingested at QC.
  To populate embeddings for products that predate the feature (or after
  enabling a provider), run the batched, idempotent backfill:

  ```powershell
  uv run --project apps/api python -m coeus.tools.backfill_embeddings
  ```

- Outside `local`/`test`, start-up fails closed if session/CSRF secrets are too
  short, if secure cookies are off in staging/prod, or if dev seed users are
  enabled without overriding the default seed credential. This is by design: it
  stops a known default password ever reaching a deployed environment.

## Deployment support

Local development is the supported runtime. Docker Compose is supported locally.
GCP Cloud Run and Kubernetes are migration targets only:

- [GCP Reference Deployment](runbooks/gcp-dev-deployment.md) explains the dormant
  Terraform reference, current blockers and required migration order.
- [Kubernetes Migration](runbooks/kubernetes-migration.md) explains what the
  existing images provide, a constrained evaluation topology and production
  readiness gates.

Neither cloud path is ready to apply today. Do not add personal project IDs,
billing details or cloud secrets to committed files.

## Troubleshooting

- **Login returns "Authentication failed" right after starting the API.** The
  first request can race the server start; wait a second and retry.
- **CORS or preflight errors in the browser.** Make sure the web origin matches
  the API's allow-list. If you run the web app on a non-default port, set the
  API's `COEUS_ALLOWED_CORS_ORIGINS` to include that origin.
- **`pnpm` not found.** Use `corepack pnpm ...`; pnpm is provided by Corepack and
  may not be on the global PATH.
- **Stale session after changing persistence mode.** Sign out and in again. If
  you need a clean local state, stop the API and delete `.local-data`.
