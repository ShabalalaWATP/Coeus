# CI/CD Pipeline Runbook

## Current Pipeline

The repository uses GitHub Actions for pull-request and `main` branch checks.

| Workflow | Trigger | Purpose |
|---|---|---|
| `Backend CI` | pull request, push to `main` | Ruff format, Ruff lint, mypy, pytest coverage, Bandit and pip-audit. |
| `Frontend CI` | pull request, push to `main` | ESLint, TypeScript, Vitest coverage, Vite build and Playwright Chromium smoke. |
| `CodeQL` | pull request, push to `main`, weekly schedule | GitHub CodeQL analysis for Python and JavaScript/TypeScript. |
| `Semgrep` | pull request, push to `main`, weekly schedule | Semgrep SAST over application source, Dockerfiles and GitHub config, with SARIF upload. |
| `Dependency Review` | pull request | Blocks pull requests that introduce high-severity vulnerable dependencies. |

Dependabot runs weekly for GitHub Actions, npm and pip dependencies. Each ecosystem has a 7-day cooldown for version updates.

## Required Status Checks

After the workflows have run on GitHub, configure `main` branch protection to require:

- `Backend CI / backend`
- `Frontend CI / frontend`
- `CodeQL / analyse (python)`
- `CodeQL / analyse (javascript-typescript)`
- `Semgrep / semgrep`
- `Dependency Review / dependency-review`

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

## Deployment

No production deployment target is configured yet. Add deployment only after the target environment, hosting model, secrets, rollback process and approval requirements are agreed.

When deployment exists, use a separate workflow or job that:

- runs only after all CI and security jobs pass
- targets a named GitHub Environment such as `staging` or `production`
- requires environment approvals for production
- uses repository or environment secrets, never committed files
- publishes immutable artefacts or container images
- records the deployed Git SHA
- has a documented rollback command
