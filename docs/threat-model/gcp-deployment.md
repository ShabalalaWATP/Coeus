# GCP Deployment Threat Model

## Scope

Sprint 12 GCP dev deployment scaffolding, Terraform, GitHub Actions deployment,
Cloud Run API/web services, Cloud SQL, Cloud Storage, Secret Manager, Pub/Sub,
Artifact Registry and supported AI provider configuration.

## Assets

- GitHub OIDC trust boundary and deployer service account.
- Terraform state and plans.
- Secret Manager secret values.
- Cloud SQL data.
- Product asset buckets.
- Pub/Sub topics and dead-letter subscriptions.
- Artifact Registry images.
- Cloud Run runtime configuration.

## Threats And Controls

| Threat | Control In Sprint 12 |
|---|---|
| Long-lived GCP key leaks from GitHub or local machines. | Deployment uses Workload Identity Federation and GitHub OIDC, not service account key JSON. |
| Secrets enter the public repository or Terraform state. | Terraform creates secret placeholders only; values are added as Secret Manager versions outside Terraform. |
| GitHub OIDC token is accepted from another repository or branch. | Workload Identity Provider condition restricts `assertion.sub`, repository and repository owner to the configured `main` branch. |
| Runtime service account has broad cloud access. | API service account receives scoped Cloud SQL, Secret Manager, bucket and Pub/Sub roles needed for dev. AI providers use explicit application configuration rather than broad cloud IAM by default. |
| Public Cloud Run API bypasses app authorisation. | Cloud Run is publicly invokable for browser access, but backend RBAC and CSRF checks still protect application actions. |
| Product assets become public. | Buckets enforce public access prevention and uniform bucket-level access. |
| Bucket access is not auditable. | Cloud Storage buckets write access logs to a dedicated dev access-log bucket. |
| Artifact Registry or Pub/Sub content uses only provider-managed encryption. | Artifact Registry and Pub/Sub topics use a customer-managed KMS key in the dev baseline. |
| Cloud SQL accepts public network traffic. | Cloud SQL public IPv4 is disabled; Cloud Run uses the Cloud SQL connection mount. |
| Worker failures are lost. | Pub/Sub worker subscriptions use retry policy and dead-letter topics. |
| Unconfigured deploy workflow fails protected-main pushes. | Dev deploy auto-run is disabled unless `GCP_DEPLOY_DEV_ENABLED=true`; manual dispatch validates required variables. |

## Open Risks

- Cloud SQL still needs persistent repositories and migrations before production
  use.
- Terraform remote state and state locking are not configured in Sprint 12.
- Public API ingress is acceptable for dev browser access but must be reviewed
  again before staging or production.
