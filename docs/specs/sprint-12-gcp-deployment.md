# Sprint 12 Spec: Future GCP Migration Reference

## Goal

Keep a reviewable future GCP migration baseline without making GCP a supported
current runtime or introducing cloud dependencies in domain code.

## Scope

- Terraform dev baseline under `infra/gcp/environments/dev`.
- Modular Terraform for project services, IAM, Artifact Registry, Cloud Run,
  Cloud SQL, Cloud Storage, Secret Manager and Pub/Sub.
- Manual migration-reference validation workflow with local image builds only.
- Production web container image for Cloud Run.
- API runtime configuration for GCP, GCS, Pub/Sub and supported AI provider settings.
- GitHub Actions Terraform validation.
- Deployment runbook updates.

## Out Of Scope

- Live `terraform apply` from Codex.
- Automatic deployment on pushes or schedules.
- A supported hosted Coeus runtime before the migration readiness gates pass.
- Production or staging environments.
- Real secret values, service account keys or personal GCP credentials.
- Persistent database repositories and migrations.
- Terraform remote state backend.
- Container vulnerability scanning, SBOM and ZAP. These remain Sprint 13.

## Acceptance Criteria

- Terraform files format and validate in CI with no GCP credentials.
- Dev Terraform can create the planned resource shell once a maintainer has
  authenticated to GCP and supplied required secret versions.
- GitHub Actions uses Workload Identity Federation, not service account keys.
- The reference workflow runs only after explicit manual confirmation and has
  no cloud authentication, push, infrastructure change or deployment step.
- Terraform apply fails unless the documented migration-readiness gate is
  deliberately lifted after every readiness control is implemented.
- The stateful API reference is constrained to one instance; Terraform rejects
  a single-writer API configured above one instance.
- Runtime GCP settings are exposed through typed application settings and
  covered by tests.
- Secret values are represented only by names in repository files.

## Verification

- Backend Ruff, mypy and pytest.
- Frontend formatting, linting, type checking, tests, build and e2e smoke.
- Terraform fmt and validate, either locally or in GitHub Actions.
- Semgrep over application, Docker, Terraform and GitHub workflow files.
- File line-limit check.
