# GitHub Branch Protection Runbook

Target repository: `ShabalalaWATP/Coeus`

## Main Branch Rule

Configure `main` with:

- Require a pull request before merging.
- Use `0` required approvals while this is a solo setup, but raise this to at least `1` and enable CODEOWNERS review once another reviewer is available.
- Dismiss stale approvals once approvals are required.
- Require all conversations resolved.
- Require linear history.
- Block force pushes.
- Block branch deletion.
- Require status checks to pass.
- Require code scanning results from CodeQL and Semgrep OSS for high-or-higher security alerts.

## Required Checks

Current checks:

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

Enable in repository settings:

- secret scanning
- push protection

Code scanning tools to require where GitHub offers them in the ruleset UI:

- CodeQL, high or higher security alerts, errors
- Semgrep OSS, high or higher security alerts, errors
- Trivy, high or higher security alerts, errors
- Checkov, high or higher security alerts, errors

Optional future checks:

- dependency review after Dependency Graph and GitHub Advanced Security support are available for the repository
- deployment checks once GCP hosting is activated

## Notes

Repository settings are GitHub-enforced state and cannot be proved by local files alone. This runbook documents the expected settings; a maintainer must configure or verify them in GitHub.
