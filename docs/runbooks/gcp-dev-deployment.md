# GCP Dev Deployment Runbook

## Safe Values To Share With Codex

You can share these identifiers when setting up the dev deployment:

- GCP project ID.
- GCP project number.
- Region.
- GitHub repository name.
- Workload Identity Provider resource name.
- Deployer service account email.
- Cloud Run service names.
- Artifact Registry repository ID.
- Public web URL for CORS.

Do not share service account key JSON, database passwords, session secrets,
CSRF secrets, OAuth client secrets or API keys in chat.

## Bootstrap

```powershell
cd infra/gcp/environments/dev
terraform init
terraform fmt -recursive
terraform validate
terraform plan -out coeus-dev.tfplan
```

Apply the non-secret infrastructure, then add Secret Manager versions for:

```text
coeus-dev-database-url
coeus-dev-session-secret
coeus-dev-csrf-secret
coeus-dev-llm-provider-config
coeus-dev-object-storage-config
```

Use GCP Secret Manager or `gcloud secrets versions add`. Do not commit those
values or put them in Terraform variable files.

## GitHub Environment Variables

Set these variables on the protected `dev` GitHub Environment:

```text
GCP_PROJECT_ID=coeus-501415
GCP_REGION=europe-west2
GCP_ARTIFACT_REPOSITORY=coeus
GCP_API_SERVICE=coeus-dev-api
GCP_WEB_SERVICE=coeus-dev-web
GCP_WORKLOAD_IDENTITY_PROVIDER=<terraform output>
GCP_DEPLOY_SERVICE_ACCOUNT=<terraform output>
GCP_DEPLOY_DEV_ENABLED=false
```

Run the `Deploy Dev` workflow manually first. Set
`GCP_DEPLOY_DEV_ENABLED=true` only after a manual deployment succeeds.

## Rollback

List recent revisions:

```powershell
gcloud run revisions list --service coeus-dev-api --region europe-west2
gcloud run revisions list --service coeus-dev-web --region europe-west2
```

Route traffic back to a known-good revision:

```powershell
gcloud run services update-traffic coeus-dev-api `
  --region europe-west2 `
  --to-revisions REVISION_NAME=100
```
