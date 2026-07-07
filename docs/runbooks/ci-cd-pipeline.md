# CI/CD Pipeline Runbook

This is the source of truth for GitHub Actions, status checks and repository
security gates. Keep the root README high-level and link here instead of listing
individual scanners there.

## Current Pipeline

The repository uses GitHub Actions for pull-request and `main` branch checks.

| Workflow | Trigger | Purpose |
|---|---|---|
| `Backend CI` | pull request, push to `main` | Ruff format, Ruff lint, mypy, pytest coverage, Bandit and pip-audit. |
| `Frontend CI` | pull request, push to `main` | ESLint, TypeScript, Vitest coverage, Vite build and Playwright Chromium smoke. |
| `CodeQL` | pull request, push to `main`, weekly schedule | GitHub CodeQL analysis for Python and JavaScript/TypeScript. |
| `Semgrep` | pull request, push to `main`, weekly schedule | Semgrep SAST over application source, Dockerfiles and GitHub config, with SARIF upload. |
| `Terraform IaC` | pull request, push to `main` | Terraform fmt, init without backend and validate for the dev environment. |
| `IaC Security` | pull request, push to `main`, weekly schedule | Checkov Terraform scan with SARIF upload. |
| `Container Security` | pull request, push to `main`, weekly schedule | Docker image build and Trivy vulnerability scanning for API and web images. |
| `Supply Chain Security` | pull request, push to `main`, weekly schedule | Gitleaks committed-history scan and CycloneDX SBOM artifact generation. |
| `DAST Security` | pull request, push to `main`, weekly schedule | ZAP baseline scan against a local CI-hosted web target. |
| `Deploy Dev` | manual dispatch, optional push to `main` | Keyless build, push and Cloud Run deploy for a future GCP dev environment. |

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

The current app is local-first. The protected dev deployment workflow is a
reference path for a future work-owned GCP project. It uses GitHub OIDC and GCP
Workload Identity Federation, not service account key JSON. Keep deployment
disabled unless the `dev` GitHub Environment variables are configured and the
first manual deployment succeeds.

Deployment jobs must:

- run only after all CI and security jobs pass
- target a named GitHub Environment such as `dev`, `staging` or `production`
- require environment approvals for production
- use repository or environment secrets, never committed files
- publish immutable artefacts or container images
- record the deployed Git SHA
- have a documented rollback command
