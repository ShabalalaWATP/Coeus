# GitHub Branch Protection Runbook

Target repository: `ShabalalaWATP/coeus`

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

Initial Sprint 2 checks:

- `backend`
- `frontend`
- `analyse (python)`
- `analyse (javascript-typescript)`
- `semgrep`

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
