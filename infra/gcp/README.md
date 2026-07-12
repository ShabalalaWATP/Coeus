# Coeus GCP Infrastructure

Coeus is intended to run locally for day-to-day development. This folder is a
reference deployment baseline for a future work-owned GCP project, not a
requirement for using the app.

Terraform describes the future development resource shell but does not store
application secret values in Terraform state. Every cloud-creating path is
downstream of a default-deny readiness precondition, including targeted plans
and applies. The configuration remains blocked while required adapters and
distributed controls are absent.

## Dev Environment

Path: `infra/gcp/environments/dev`

Creates:

- required GCP APIs
- Workload Identity Federation for GitHub Actions
- runtime and deployer service accounts
- Artifact Registry Docker repository
- Cloud SQL PostgreSQL instance and application database shell
- private Cloud Storage buckets for products, previews and audit exports
- Pub/Sub topics, worker subscriptions and dead-letter topics
- Secret Manager placeholders
- Cloud Run services for API and web containers

The API reference is single-writer and has a maximum of one instance. The web
reference may scale independently. Terraform rejects any larger API value until
the future distributed-state readiness gates are implemented.

## Required Variables

Copy `terraform.tfvars.example` to a private, gitignored `terraform.tfvars` and
replace every placeholder with values from the work GCP project.

Do not commit `terraform.tfvars`, Terraform state, plans or secrets.

## Required Secret Values

After Terraform creates the secret placeholders, add versions for:

- `coeus-dev-database-url`
- `coeus-dev-session-secret`
- `coeus-dev-csrf-secret`
- `coeus-dev-local-seed-credential`
- `coeus-dev-llm-provider-config`
- `coeus-dev-object-storage-config`

Use Secret Manager in the GCP console or `gcloud secrets versions add`. Never put
these values in Terraform variables, GitHub workflow files, Markdown or chat.

## Future GitHub Variables

Only after every ADR 0019 readiness gate passes and a supported deployment
workflow is introduced, copy Terraform outputs into a protected GitHub
Environment named `dev`:

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GCP_ARTIFACT_REPOSITORY`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOY_SERVICE_ACCOUNT`
- `GCP_API_SERVICE`
- `GCP_WEB_SERVICE`

The current GitHub migration-reference workflow only validates Terraform and
builds both images locally. It never authenticates to GCP, pushes images,
changes infrastructure or deploys traffic. Repository pushes never run it.

## Commands

```powershell
cd infra/gcp/environments/dev
terraform init
terraform fmt -recursive
terraform validate
terraform test
terraform plan -out coeus-dev.tfplan
```

The final plan command is expected to fail while
`migration_adapters_ready = false`. Do not set it to true until every ADR 0019
readiness gate is implemented, independently reviewed and authorised for
staging validation.

Do not use `-target` as a bypass. A regression test targets the database module
and verifies that the same readiness precondition still blocks the plan.
