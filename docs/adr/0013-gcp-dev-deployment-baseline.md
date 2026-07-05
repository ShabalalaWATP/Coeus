# ADR 0013: GCP Dev Deployment Baseline

## Status

Accepted.

## Context

Sprint 12 moves Coeus from local-only delivery toward a development GCP
deployment. The repository is public-safe, so deployment code must avoid real
credentials, private endpoints and long-lived service account keys. The current
application still uses local-first service implementations, so cloud adapters
must stay behind configuration and integration boundaries.

## Decision

Use Terraform modules under `infra/gcp` for the dev resource baseline:

- Project services, IAM, Workload Identity Federation and service accounts.
- Artifact Registry for immutable container images.
- Cloud Run for API and web services.
- Cloud SQL PostgreSQL, Cloud Storage, Secret Manager and Pub/Sub.

GitHub Actions deploys to dev with OIDC-backed Workload Identity Federation
through a deployer service account. Secret values are created as Secret Manager
versions outside Terraform. Terraform creates only secret placeholders and IAM
bindings. The app exposes GCP, Gemma Vertex, GCS and Pub/Sub runtime settings
without importing GCP SDKs into domain services.

## Consequences

- No service account key JSON is needed for CI/CD.
- Terraform state does not contain application secret values.
- Dev deployment can be bootstrapped safely, but it needs a documented two-step
  process: create Secret Manager resources, add versions, then deploy services.
- Cloud-specific behaviour remains isolated for later persistent adapters.
- Container scanning, DAST, SBOM and Terraform security scanning remain Sprint
  13 hardening work.
