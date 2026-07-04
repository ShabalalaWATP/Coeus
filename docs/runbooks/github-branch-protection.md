# GitHub Branch Protection Runbook

Target repository: `ShabalalaWATP/coeus`

## Main Branch Rule

Configure `main` with:

- Require a pull request before merging.
- Require at least 2 approvals.
- Require CODEOWNERS review.
- Dismiss stale approvals.
- Require all conversations resolved.
- Require linear history.
- Block force pushes.
- Block branch deletion.
- Require status checks to pass.

## Required Checks

Initial Sprint 2 checks:

- `Backend CI / backend`
- `Frontend CI / frontend`
- `CodeQL / analyse (python)`
- `CodeQL / analyse (javascript-typescript)`
- `Semgrep / semgrep`

Enable in repository settings:

- secret scanning
- push protection

Future checks from the implementation plan should be added as their workflows land:

- container scan
- dependency review after Dependency Graph and GitHub Advanced Security support are available for the repository
- Terraform scan
- ZAP baseline
- deployment checks

## Notes

Repository settings are GitHub-enforced state and cannot be proved by local files alone. This runbook documents the expected settings; a maintainer must configure or verify them in GitHub.
