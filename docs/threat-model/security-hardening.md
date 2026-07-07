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
| Generic workflow permissions expose unrelated tickets. | Customer ticket listing is owner/admin scoped; routing, analyst and QC services use workflow-specific reads plus route, assignment or QC-state predicates. |
| Product metadata bypasses store object policy. | Feedback analytics resolves reuse and feedback product titles through store detail policy before returning metadata. |
| QC approval assigns arbitrary active ACGs. | Auto-ingestion accepts only active ACGs that are already in the ticket project scope, the QC actor's active ACG memberships or a restricted-read role. |
| Non-canonical owner-team input bypasses team permissions. | Product creation normalises managed owner teams and rejects unknown owner-team values before permission checks. |
| Username spraying clears active lockouts. | Bounded login-attempt eviction skips unexpired lockout records and drops only unlocked or expired entries. |
| Shared browser sessions expose cached protected data. | The app-level auth provider clears the React Query cache on login, logout and session expiry transitions. |

## Cross-Cutting Review

Existing sprint threat models were reviewed against the Sprint 13 gates. The
new controls reinforce repository, CI, deployment-scaffold, intake and cloud
configuration risks without changing the local-first application trust model.

## Review Hardening (2026-07-06)

Following code-quality and defensive-security reviews, the following controls
were added and are covered by tests.

| Threat | Mitigation |
| --- | --- |
| A public deployment boots with the source-committed default seed password and grants free administrator access. | Start-up now fails closed when dev seed users are enabled and `COEUS_LOCAL_SEED_CREDENTIAL` is left at its default, alongside the existing session/CSRF/secure-cookie checks (`core/config.py`). |
| On-path downgrade or clickjacking against browser clients. | The API sets a narrow `Content-Security-Policy` (`frame-ancestors 'none'; base-uri 'none'`) always and `Strict-Transport-Security` when serving over TLS; the browser-facing nginx config sets a full resource CSP plus HSTS (`core/security.py`, `infra/docker/nginx-web.conf`). |
| A client-supplied asset name escapes its object-key prefix once real storage is wired in. | Asset object keys reduce the name to a single safe path segment via `object_key_segment`, stripping directory components and parent references (`domain/store.py`, used by store and QC ingestion). |
| A client declares an implausible asset size to bypass future quota logic. | `StoreAssetRequest.size_bytes` now has an upper bound at the schema boundary in addition to the service-layer positive-size check. |
| Long list item strings amplify request size or get persisted into workflow records. | Store metadata arrays, routing clarification questions, analyst assignment work-package titles and admin role names now bound each item as well as list length. |
| Reserved characters in browser route IDs or API path IDs cause path confusion. | Frontend API clients encode dynamic path segments, and local navigation links encode request, project, task, QC, product and asset IDs before constructing routes. |
| Cross-task data association in the analyst workbench, or a stale routing selection after a ticket leaves the queue. | Frontend state is reset on selection change (analyst detail keyed by task; routing selection cleared when a ticket is routed away), preventing one task's draft being submitted against another. |

## Open Risks

- Distributed rate limiting is still required before a public multi-instance
  deployment, even though local IP-based login throttling exists.
- Store uploads still need malware scanning and stronger MIME verification
  before accepting untrusted production files.
- Native GitHub secret scanning and push protection are repository settings and
  must be confirmed in GitHub, not by local files alone.
- ZAP is unauthenticated. It does not prove role-protected flows are free from
  dynamic findings.
- Container scan results depend on the current vulnerability databases and may
  change between scheduled runs.
- Live GCP hosting remains parked, so cloud runtime controls are not validated
  against deployed resources.
