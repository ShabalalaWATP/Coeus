# Istari

Istari is a security-conscious, role-based platform for intelligence tasking
and product orchestration: it routes customer requests, tasks analysts, and
releases quality-assured products. Security-sensitive and workflow-changing
actions are audited. The product brand is
Istari; internal package, module and infrastructure identifiers keep the
original `coeus` working name.

![Istari sign-in and splash page](docs/images/01-splash-login.png)

## What it does

- **Search before you task.** An RFI agent offers existing products before any
  new work is raised.
- **Conversational intake.** An assistant captures a complete requirement from a
  chat, not a long form.
- **Managed end to end.** Requests route through assessment or collection review,
  analyst production, manager review and final quality-control release.
- **Controlled by design.** Role-based access, need-to-know access control
  groups and clearance levels, with security-sensitive and workflow-changing
  actions audited.
- **Bounded automation, human-governed.** Deterministic services extract, search
  and enforce workflow gates. The active JIOC Agent may route an eligible request
  to CM or RFA; people remain in the loop for requester choices, delivery
  approvals, release and exception review. JIOC Managers oversee routine routing
  on the loop and can hold, reopen or refer cases through audited controls. See
  [AI Agents](docs/AI_AGENTS.md).

## Documentation

New here? Start with the [documentation index](docs/README.md).

| Guide                                                    | Read it for                                                              |
| -------------------------------------------------------- | ------------------------------------------------------------------------ |
| [Setup Guide](docs/SETUP.md)                             | Prerequisites, running locally, seed accounts, checks                    |
| [Architecture](docs/ARCHITECTURE.md)                     | System structure, the request journey, and local and future GCP diagrams |
| [User Guide](docs/USER_GUIDE.md)                         | Current key-workspace screenshots and role workflows                     |
| [Roles and User Stories](docs/ROLES_AND_USER_STORIES.md) | Roles, permissions, need-to-know groups, user stories                    |
| [AI Agents](docs/AI_AGENTS.md)                           | What each agent reads, decides and returns                               |
| [Runbooks](docs/README.md#runbooks)                      | Local development, CI/CD, branch protection and deployment references    |

## Quick start

Istari is currently intended to run locally on a developer machine using
PostgreSQL for application state, with relational Intelligence Store tables and
pgvector-ready search indexes matching the future Cloud SQL for PostgreSQL
direction. Store product metadata, assets, ACG joins and semantic labels are
mirrored into those relational tables when the local PostgreSQL provider is
enabled. Uploaded assets are stored on the local filesystem for now. Full
instructions are in the [Setup Guide](docs/SETUP.md).

```powershell
# Install
uv sync --project apps/api --all-groups
corepack pnpm install

# Local runtime configuration
Copy-Item .env.example .env

# Start local PostgreSQL, then run the API and web app
docker compose up -d postgres
uv run --project apps/api uvicorn coeus.main:app --host 127.0.0.1 --port 8001 --workers 1
corepack pnpm --filter @coeus/web dev
```

Open <http://127.0.0.1:5173> and sign in as `user@example.test` with the mock
credential `CoeusLocal1!`. The full list of seed accounts is in the
[Setup Guide](docs/SETUP.md#seed-accounts).

## Tech stack

- **Backend:** Python 3.12+, FastAPI, Pydantic v2, PostgreSQL, Alembic,
  pgvector-ready Store schema, local object storage, managed with `uv`.
- **Frontend:** React 19, Vite, TypeScript, React Router, TanStack Query,
  react-hook-form, Zod; tested with Vitest and Playwright.
- **Quality gates:** ruff, mypy, ESLint, Prettier, tsc, OpenAPI contract drift,
  a 350-line file limit, and at least 95% line and branch coverage on both
  backend and frontend.

## Project structure

```
apps/
  api/    FastAPI backend (src/coeus: domain, repositories, services, schemas, api)
  web/    React + Vite frontend (src/features, src/lib, src/app)
docs/     Guides, specs, ADRs, threat models, runbooks, screenshots
infra/    Docker runtime files and dormant GCP Terraform reference
scripts/  Local development and seeding helpers
```

## Security and repository safety

- Treat every part of this repository as security-sensitive. Authorisation is
  enforced server-side at the object and action level.
- All data is synthetic. Do not commit real intelligence products, real
  operational examples, private URLs, credentials, classified strings, internal
  schemas or personal account details. Screenshots in [docs/images](docs/images)
  are of synthetic, clearly labelled **MOCK DATA ONLY** content; never commit a
  screenshot of real intelligence.
- Per-feature threat models are listed in the
  [threat-model index](docs/threat-model/README.md).

## Operations

Operational detail is kept in linked runbooks so this README stays focused on
what the product is and how to start it:

- [CI/CD Pipeline Runbook](docs/runbooks/ci-cd-pipeline.md) covers GitHub
  Actions, required checks and security gates.
- [GitHub Branch Protection Runbook](docs/runbooks/github-branch-protection.md)
  covers the `main` ruleset and pull-request requirements.
- [GCP Reference Deployment Runbook](docs/runbooks/gcp-dev-deployment.md) covers
  the future work-owned cloud deployment path.
- [Kubernetes Migration Guide](docs/runbooks/kubernetes-migration.md) records the
  reusable container boundaries and the work required before cluster deployment.

The app does not require GCP for local use. Do not put service account keys,
database passwords, runtime secrets or personal cloud account details in
repository files.

Local development is the only supported runtime today. Docker Compose is
supported for local use; GCP and Kubernetes are documented migration targets,
not active deployment options.
