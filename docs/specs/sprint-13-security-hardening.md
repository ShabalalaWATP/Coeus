# Sprint 13 Spec: Security Hardening

## Goal

Close the MVP security-hardening sprint by making security checks visible,
repeatable and enforceable before code reaches `main`.

## In Scope

- CodeQL hardening with the extended and security-and-quality suites.
- Semgrep hardening with `auto` and OWASP Top 10 rules.
- Dependabot coverage for GitHub Actions, npm, pip, Docker and Terraform.
- Gitleaks secret scanning in CI and documented GitHub push protection.
- Trivy container vulnerability scanning for API and web images.
- CycloneDX SBOM generation.
- ZAP baseline scan against a local CI-hosted web target.
- Checkov Terraform scanning with SARIF upload.
- Prompt-injection regression suite for the mock intake boundary.
- Full threat-model pass and air-gapped deployment notes.

## Out Of Scope

- Live GCP deployment, DNS, certificates or production hosting.
- Authenticated DAST crawling.
- Production incident-response processes.
- Replacing local-first repositories with persistent database adapters.

## Acceptance Criteria

- Pull requests run backend, frontend, CodeQL, Semgrep, secret scanning, SBOM,
  Trivy, Checkov and ZAP checks.
- Code scanning uploads SARIF for CodeQL, Semgrep, Trivy and Checkov where
  GitHub permits SARIF upload for the event.
- Terraform security scan passes with only documented dev-scope exceptions.
- Prompt-injection tests cover system-prompt leakage, admin escalation, RBAC
  bypass, tool-call abuse, jailbreak wording and fabricated product matches.
- Security runbooks list required branch-protection checks and manual GitHub
  repository security settings.
- The air-gapped runbook explains how to package source, images, SBOMs and
  scanner evidence without committing secrets.
