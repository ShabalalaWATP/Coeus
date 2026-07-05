# Security Hardening Threat Model

## Scope

Sprint 13 CI/CD security gates, static analysis, secret scanning, container
scanning, SBOM generation, Terraform scanning, baseline DAST and prompt
injection regression coverage.

## Assets

- GitHub Actions workflow identity and repository contents.
- Code scanning SARIF uploads.
- Container images built from `infra/docker`.
- Terraform modules under `infra/gcp`.
- SBOM artifacts.
- ZAP baseline reports.
- Prompt-injection regression evidence.

## Threats And Controls

| Threat | Sprint 13 control |
|---|---|
| Vulnerable code reaches `main` without static analysis. | CodeQL extended queries and Semgrep `auto` plus OWASP Top 10 run on pull requests, `main` pushes and schedules. |
| Secrets are committed or retained in history. | Gitleaks scans committed history in CI; GitHub secret scanning and push protection remain required repository settings. |
| Container base images include known fixable vulnerabilities. | Trivy scans API and web images for high and critical OS and library vulnerabilities. |
| Infrastructure drift introduces insecure Terraform. | Checkov scans `infra/gcp` and uploads SARIF; inline skips document accepted dev-scope exceptions. |
| Frontend exposes unauthenticated passive DAST issues. | ZAP baseline scans a locally built web target in CI without touching GCP. |
| Dependency inventory is unavailable during review. | CycloneDX SBOM artifact is generated on each security supply-chain run. |
| User prompt text escalates authority or exposes hidden instructions. | Prompt-injection tests cover system-prompt leakage, RBAC bypass, admin claims, jailbreak wording, tool abuse and fabricated product matches. |
| Scanner reports are ignored because they are out of band. | SARIF uploads make CodeQL, Semgrep, Trivy and Checkov visible in GitHub code scanning where event permissions allow. |

## Cross-Cutting Review

Existing sprint threat models were reviewed against the Sprint 13 gates. The
new controls reinforce repository, CI, deployment-scaffold, intake and cloud
configuration risks without changing the local-first application trust model.

## Open Risks

- Native GitHub secret scanning and push protection are repository settings and
  must be confirmed in GitHub, not by local files alone.
- ZAP is unauthenticated. It does not prove role-protected flows are free from
  dynamic findings.
- Container scan results depend on the current vulnerability databases and may
  change between scheduled runs.
- Live GCP hosting remains parked, so cloud runtime controls are not validated
  against deployed resources.
