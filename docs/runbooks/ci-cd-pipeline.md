# CI/CD Pipeline Runbook

## Current Pipeline

The repository uses GitHub Actions for pull-request and `main` branch checks.

| Workflow | Trigger | Purpose |
|---|---|---|
| `Backend CI` | pull request, push to `main` | Ruff format, Ruff lint, mypy, pytest coverage, Bandit and pip-audit. |
| `Frontend CI` | pull request, push to `main` | ESLint, TypeScript, Vitest coverage, Vite build and Playwright Chromium smoke. |
| `CodeQL` | pull request, push to `main`, weekly schedule | GitHub CodeQL analysis for Python and JavaScript/TypeScript. |
| `Semgrep` | pull request, push to `main`, weekly schedule | Semgrep SAST over application source, Dockerfiles and GitHub config, with SARIF upload. |
| `Terraform IaC` | pull request, push to `main` when GCP files change | Terraform fmt, init without backend and validate for the dev environment. |
| `Deploy Dev` | manual dispatch, optional push to `main` | Keyless build, push and Cloud Run deploy for the GCP dev environment. |

Dependabot runs weekly for GitHub Actions, npm and pip dependencies. Each ecosystem has a 7-day cooldown for version updates. npm semver-major version updates are ignored during this milestone and should be handled as planned upgrade work with migration notes, not automatic dependency PRs.

## Required Status Checks

After the workflows have run on GitHub, configure the `protect main` ruleset to require these exact check-run contexts:

- `backend`
- `frontend`
- `analyse (python)`
- `analyse (javascript-typescript)`
- `semgrep`
- `terraform`

GitHub only offers checks that have recently run in the repository, so push the workflow commit first, let the checks complete, then add them to the branch protection rule.

## Repository Security Settings

Enable these GitHub repository settings:

- Actions enabled for the repository.
- Code scanning enabled.
- Dependabot alerts enabled.
- Dependabot security updates enabled.
- Secret scanning enabled.
- Push protection enabled.
- Branch protection for `main` as described in `docs/runbooks/github-branch-protection.md`.

Dependency Review can be added later if GitHub reports it as supported for the repository. At the time this runbook was written, GitHub reported that Dependency Review was not supported without Dependency Graph and GitHub Advanced Security support for the repository.

## Deployment

Sprint 12 adds a protected dev deployment workflow. It uses GitHub OIDC and GCP
Workload Identity Federation, not service account key JSON. Keep the workflow
manual until the `dev` GitHub Environment variables are configured and the first
deployment succeeds.

Deployment jobs must:

- run only after all CI and security jobs pass
- target a named GitHub Environment such as `dev`, `staging` or `production`
- require environment approvals for production
- use repository or environment secrets, never committed files
- publish immutable artefacts or container images
- record the deployed Git SHA
- have a documented rollback command
