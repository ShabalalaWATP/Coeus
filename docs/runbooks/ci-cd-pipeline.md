# CI/CD Pipeline Runbook

This is the source of truth for GitHub Actions, status checks and repository
security gates. Keep the root README high-level and link here instead of listing
individual scanners there.

## Current Pipeline

The repository uses GitHub Actions for pull-request and `main` branch checks.

| Workflow | Trigger | Purpose |
|---|---|---|
| `Backend CI` | pull request, push to `main` | File limits, Markdown links/images, Ruff, mypy, architecture boundaries, semantic OpenAPI compatibility, generated type drift, real PostgreSQL migration/concurrency tests, independent line/branch coverage, Bandit and pip-audit. |
| `Frontend CI` | pull request, push to `main` | Prettier, ESLint, TypeScript, Knip, all Vitest coverage gates, production audit, Vite build, fast Playwright journeys and the disposable-PostgreSQL security workflow. |
| `CodeQL` | pull request, push to `main`, weekly schedule | GitHub CodeQL analysis for Python and JavaScript/TypeScript. |
| `Semgrep` | pull request, push to `main`, weekly schedule | Semgrep SAST over application source, Dockerfiles and GitHub config, with SARIF upload. |
| `Terraform IaC` | pull request, push to `main` | Terraform fmt, init without backend and validate for the dev environment. |
| `IaC Security` | pull request, push to `main`, weekly schedule | Checkov Terraform scan with SARIF upload. |
| `Container Security` | pull request, push to `main`, weekly schedule | Docker image build and Trivy vulnerability scanning for API and web images. |
| `Supply Chain Security` | pull request, push to `main`, weekly schedule | Gitleaks committed-history scan and CycloneDX SBOM artifact generation. |
| `DAST Security` | pull request, push to `main`, weekly schedule | Fail-closed ZAP baseline scan against a local CI-hosted web target using a reviewed rules file. |
| `Future GCP Migration Reference` | manual dispatch only | Future-migration Terraform tests and local image builds. It does not authenticate, push, change infrastructure or deploy. |

The PostgreSQL browser gate is `pnpm playwright:postgres`. It creates a unique
database from `COEUS_TEST_DATABASE_URL`, migrates it to Alembic head, runs the
real API and web applications, exercises draft denial, `413` and `429` recovery
through release and verifies downloaded bytes, then terminates connections and
drops the database.
The ordinary `test:e2e` suite remains the faster memory-backed compatibility
and UI smoke gate. Neither local gate is staging evidence.

Dependabot runs weekly for GitHub Actions, npm, pip, Docker and Terraform
dependencies. Each ecosystem has a 7-day cooldown for version updates. npm
semver-major version updates are ignored during this milestone and should be
handled as planned upgrade work with migration notes, not automatic dependency
PRs.

## Required Status Checks

After the workflows have run on GitHub, configure the `protect main` ruleset to
require these exact check-run contexts:

- `backend`
- `frontend`
- `analyse (python)`
- `analyse (javascript-typescript)`
- `semgrep`
- `terraform`
- `checkov`
- `trivy`
- `gitleaks`
- `sbom`
- `zap-baseline`

GitHub only offers checks that have recently run in the repository. Push the
workflow commit first, let the checks complete, then add them to the branch
protection rule.

## Repository Security Settings

Enable these GitHub repository settings:

- Actions enabled for the repository.
- Code scanning enabled.
- Dependabot alerts enabled.
- Dependabot security updates enabled.
- Secret scanning enabled.
- Push protection enabled.
- Code scanning required for CodeQL, Semgrep, Trivy and Checkov high-or-higher
  security results where GitHub exposes those tools in the ruleset UI.
- Branch protection for `main` as described in `docs/runbooks/github-branch-protection.md`.

Dependency Review can be added if GitHub reports it as supported for the
repository. Treat it as an optional repository setting unless it appears as an
available required check.

## Deployment

The current app is local-first. No current workflow may authenticate to GCP,
push images, change infrastructure or deploy traffic. The dev workflow is an
inactive migration-reference validator and local builder only.

Any future deployment job requires a separate authorised migration milestone
and must:

- run only after all CI and security jobs pass
- target a named GitHub Environment such as `dev`, `staging` or `production`
- require environment approvals for production
- use repository or environment secrets, never committed files
- publish immutable artefacts or container images
- record the deployed Git SHA
- have a documented rollback command

## ZAP Required-Gate Policy

- Do not pass `-I`; warning exit codes must reach `fail_action: true`.
- Maintain a reviewed rules file that explicitly classifies FAIL, WARN and
  justified IGNORE rules.
- Run a controlled vulnerable fixture and prove `zap-baseline` fails while its
  report and local target logs remain available.
- Verify the live GitHub ruleset requires the exact `zap-baseline` context.
