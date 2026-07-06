# Istari

Istari is a secure, role-based platform for intelligence tasking and product
orchestration: it routes customer requests, tasks analysts, and releases
quality-assured products, with every action audited. The product brand is
Istari; internal package, module and infrastructure identifiers keep the
original `coeus` working name.

![Istari sign-in and splash page](docs/images/01-splash-login.png)

## What it does

- **Search before you task.** An RFI agent offers existing products before any
  new work is raised.
- **Conversational intake.** An assistant captures a complete requirement from a
  chat, not a long form.
- **Managed end to end.** Requests route through assessment or collection review,
  analyst production, quality control and a manager release step.
- **Controlled by design.** Role-based access, need-to-know access control
  groups, clearance levels and a full audit trail.
- **AI-first, human-decided.** Agents extract, rank and advise; a person makes
  every decision that changes state. See [AI Agents](docs/AI_AGENTS.md).

## Documentation

New here? Start with the [documentation index](docs/README.md).

| Guide | Read it for |
| --- | --- |
| [Setup Guide](docs/SETUP.md) | Prerequisites, running locally, seed accounts, checks |
| [User Guide](docs/USER_GUIDE.md) | Screenshot walkthrough of every role's workspace |
| [Roles and User Stories](docs/ROLES_AND_USER_STORIES.md) | Roles, permissions, need-to-know groups, user stories |
| [AI Agents](docs/AI_AGENTS.md) | What each agent reads, decides and returns |

## Quick start

Istari is local-first: the backend seeds all data into in-memory repositories, so
two processes and no database are enough. Full instructions are in the
[Setup Guide](docs/SETUP.md).

```bash
# Install
uv sync --project apps/api --all-groups
corepack pnpm install

# Run the API (terminal 1) and the web app (terminal 2)
uv run --directory apps/api uvicorn coeus.main:app --host 127.0.0.1 --port 8001
corepack pnpm --filter @coeus/web dev
```

Open <http://127.0.0.1:5173> and sign in as `user@example.test` with the mock
credential `CoeusLocal1!`. The full list of seed accounts is in the
[Setup Guide](docs/SETUP.md#seed-accounts).

## Tech stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, in-memory seed repositories,
  managed with `uv`.
- **Frontend:** React 19, Vite, TypeScript, React Router, TanStack Query,
  react-hook-form, Zod; tested with Vitest and Playwright.
- **Quality gates:** ruff, mypy, ESLint, Prettier, tsc, a 350-line file limit,
  and at least 95% line and branch coverage on both backend and frontend.

## Project structure

```
apps/
  api/    FastAPI backend (src/coeus: domain, repositories, services, schemas, api)
  web/    React + Vite frontend (src/features, src/lib, src/app)
docs/     Guides, specs, ADRs, threat models, runbooks, screenshots
infra/    Docker and GCP (Terraform) scaffolding
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
- Per-feature threat models live in [docs/threat-model](docs/threat-model/).

## CI and deployment

Work lands through protected-main pull requests with required CI and security
checks: backend and frontend quality gates, CodeQL, Semgrep, Gitleaks, Checkov,
Trivy image scanning, CycloneDX SBOM generation and ZAP baseline scanning. See
[docs/runbooks/ci-cd-pipeline.md](docs/runbooks/ci-cd-pipeline.md).

GCP dev deployment is scaffolded with Terraform and GitHub Actions; start with
`infra/gcp/README.md` and
[docs/runbooks/gcp-dev-deployment.md](docs/runbooks/gcp-dev-deployment.md). Do not
put service account keys, database passwords or runtime secrets in repository
files.
