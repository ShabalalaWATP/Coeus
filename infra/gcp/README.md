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
replace every placeholder with values from the work GCP project. Before adding
values, confirm the ignore rule from the repository root:

```powershell
git check-ignore -v infra/gcp/environments/dev/terraform.tfvars
```

Do not commit `terraform.tfvars`, Terraform state, plans or secrets.

## Required Secret Values

The currently mapped runtime placeholders require reviewed values before any
future hosted start:

- `coeus-dev-database-url`
- `coeus-dev-session-secret`
- `coeus-dev-csrf-secret`
- `coeus-dev-local-seed-credential`

Terraform also declares two unused future scaffolding placeholders:

- `coeus-dev-llm-provider-config` (unused future scaffolding)
- `coeus-dev-object-storage-config` (unused future scaffolding)

Do not populate the two aggregate provider placeholders until a reviewed schema
and Cloud Run mapping exist. The current reference is still blocked because it
does not yet create or map
three secrets required by hosted startup:

- `coeus-dev-asset-token-secret` as `COEUS_ASSET_TOKEN_SECRET`
- `coeus-dev-configuration-encryption-key` as
  `COEUS_CONFIGURATION_ENCRYPTION_KEY`
- `coeus-dev-metrics-bearer-token` as `COEUS_METRICS_BEARER_TOKEN`

Add those placeholders and Cloud Run mappings before readiness approval. The
reference already sets `COEUS_JIOC_AGENT_ROUTING_ENABLED=disabled` explicitly.
Any future active mode must also map an explicit approved release list containing
the evaluated release identifier.

Use Secret Manager in the GCP console or `gcloud secrets versions add`. Never put
these values in Terraform variables, GitHub workflow files, Markdown or chat.

## Future GitHub Variables

Only after every ADR 0019 readiness gate passes and a supported deployment
workflow is introduced, configure a protected GitHub Environment named `dev`.
Project ID and region come from reviewed Terraform inputs; repository URL,
service URLs, deployer email and Workload Identity provider are outputs. API and
web service names need explicit outputs before a workflow may consume them.
Expected future variables are:

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
