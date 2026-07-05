# Coeus GCP Infrastructure

Sprint 12 adds the development GCP deployment baseline. Terraform creates the
resource shell, but does not store application secret values in Terraform state.

## Dev Environment

Path: `infra/gcp/environments/dev`

Creates:

- Required GCP APIs.
- Workload Identity Federation for GitHub Actions.
- Runtime and deployer service accounts.
- Artifact Registry Docker repository.
- Cloud SQL PostgreSQL instance and application database.
- Private Cloud Storage buckets for products, previews and audit exports.
- Pub/Sub topics, worker subscriptions and dead-letter topics.
- Secret Manager placeholders.
- Cloud Run services for API and web containers.

## Required Secret Values

Create Secret Manager versions for these secrets after `terraform apply`:

- `coeus-dev-database-url`
- `coeus-dev-session-secret`
- `coeus-dev-csrf-secret`
- `coeus-dev-llm-provider-config`
- `coeus-dev-object-storage-config`

Do not put those values in Terraform variables, GitHub workflow files, Markdown
or chat. Use the GCP console or `gcloud secrets versions add`.

## GitHub Variables

After `terraform apply`, copy these Terraform outputs into GitHub environment or
repository variables:

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GCP_ARTIFACT_REPOSITORY`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOY_SERVICE_ACCOUNT`
- `GCP_API_SERVICE`
- `GCP_WEB_SERVICE`

Enable `GCP_DEPLOY_DEV_ENABLED=true` only after the first manual deployment has
worked from the protected `dev` GitHub Environment.

## Commands

```powershell
cd infra/gcp/environments/dev
terraform init
terraform fmt -recursive
terraform validate
terraform plan -out coeus-dev.tfplan
```
