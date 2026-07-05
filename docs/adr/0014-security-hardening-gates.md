# ADR 0014: Security Hardening Gates

## Status

Accepted.

## Context

Sprint 13 needs security checks that are repeatable in GitHub Actions and useful
locally. The repository is public-safe but models an intelligence workflow, so
security regressions should be visible before merge.

## Decision

Use layered CI gates rather than a single aggregate security job:

- CodeQL runs Python and JavaScript/TypeScript analysis with extended queries.
- Semgrep scans app source, Dockerfiles, Terraform and GitHub workflows with
  `auto` and OWASP Top 10 rules.
- Gitleaks scans committed history in CI.
- Trivy scans built API and web images and uploads SARIF.
- Checkov scans Terraform and uploads SARIF.
- ZAP runs a baseline scan against a local CI-hosted web target.
- Anchore Syft produces a CycloneDX SBOM artifact.

Terraform Checkov exceptions are inline and narrow. The dev baseline accepts
PostgreSQL 16 pinning and deferred GCS access-log sink configuration until GCP
hosting is activated. The GitHub OIDC condition is branch-bound, but Checkov
cannot resolve the module variable inside the subject claim, so it has a local
skip with the condition kept in code.

## Consequences

- Branch protection can require concrete check-run contexts for security gates.
- Security evidence is attached to pull requests and scheduled runs.
- ZAP remains unauthenticated until a safe seeded login flow is added for DAST.
- Container scanning depends on Docker availability in GitHub-hosted runners.
