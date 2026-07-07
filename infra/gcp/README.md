# Coeus GCP Infrastructure

Coeus is intended to run locally for day-to-day development. This folder is a
reference deployment baseline for a future work-owned GCP project, not a
requirement for using the app.

Terraform creates the development resource shell but does not store application
secret values in Terraform state.

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

## GitHub Variables

After `terraform apply`, copy Terraform outputs into the protected GitHub
Environment named `dev`:

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GCP_ARTIFACT_REPOSITORY`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOY_SERVICE_ACCOUNT`
- `GCP_API_SERVICE`
- `GCP_WEB_SERVICE`

Keep `GCP_DEPLOY_DEV_ENABLED=false` until the first manual deployment succeeds.

## Commands

```powershell
cd infra/gcp/environments/dev
terraform init
terraform fmt -recursive
terraform validate
terraform plan -out coeus-dev.tfplan
```
