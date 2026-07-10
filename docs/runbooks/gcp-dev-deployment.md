# GCP Reference Deployment Runbook

Coeus runs locally by default. This runbook is a reference for a future
work-owned GCP development deployment. Do not use personal GCP account details,
personal project IDs or personal billing accounts in committed files.

## What This Deploys

- Cloud Run service for the FastAPI API.
- Cloud Run service for the React web container.
- Artifact Registry Docker repository.
- Cloud SQL PostgreSQL database shell.
- Cloud Storage buckets for future product assets and previews.
- Pub/Sub topics for future workers.
- Secret Manager placeholders.
- GitHub Actions authentication through Workload Identity Federation.

Current limitation: the local app now has file and PostgreSQL state-store
adapters, but this runbook remains a reference path. GCS, Pub/Sub and production
worker adapters still need implementation before a full hosted deployment.
Do not execute this runbook until ADR 0019's migration readiness gates pass.
The reference API is intentionally limited to one instance.

## Values You Need

Collect these from the work GCP project and GitHub repository:

```text
PROJECT_ID=<work-gcp-project-id>
PROJECT_NUMBER=<numeric-project-number>
REGION=europe-west2
GITHUB_REPOSITORY=<github-owner>/<repo-name>
```

Safe to share with Codex or in tickets:

- project ID and project number
- region
- GitHub repository name
- Cloud Run service names
- Artifact Registry repository ID
- Workload Identity Provider resource name
- deployer service account email

Never share or commit:

- service account key JSON
- database passwords
- session or CSRF secrets
- OAuth/client/API keys
- Terraform state files or plans

## Install Local Tools

On Windows PowerShell:

```powershell
(New-Object Net.WebClient).DownloadFile(
  "https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe",
  "$env:TEMP\GoogleCloudSDKInstaller.exe"
)
& "$env:TEMP\GoogleCloudSDKInstaller.exe"
```

Close and reopen PowerShell, then check:

```powershell
gcloud --version
terraform -version
docker version
```

Authenticate:

```powershell
gcloud init
gcloud auth application-default login
gcloud config set project <PROJECT_ID>
gcloud projects describe <PROJECT_ID> --format="value(projectNumber)"
```

The last command must print `<PROJECT_NUMBER>`.

## Prepare Terraform Variables

Copy the example file, but do not commit the copy:

```powershell
cd C:\path\to\Coeus\infra\gcp\environments\dev
Copy-Item terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
project_id        = "<PROJECT_ID>"
project_number    = "<PROJECT_NUMBER>"
region            = "europe-west2"
environment       = "dev"
github_repository = "<GITHUB_OWNER>/<REPO>"

api_image = "europe-west2-docker.pkg.dev/<PROJECT_ID>/coeus/coeus-api:bootstrap"
web_image = "europe-west2-docker.pkg.dev/<PROJECT_ID>/coeus/coeus-web:bootstrap"

allowed_cors_origins = []

cloud_sql_deletion_protection = false
```

## Create The Core Resource Shell

```powershell
terraform init
terraform fmt -recursive
terraform validate

terraform apply `
  -target=module.project_services `
  -target=module.iam `
  -target=module.kms `
  -target=module.artifact_registry `
  -target=module.secrets `
  -target=module.storage `
  -target=module.pubsub `
  -target=module.database
```

Type `yes` when the plan matches the expected resources.

## Add Secret Manager Versions

Add versions for these secrets:

```text
coeus-dev-database-url
coeus-dev-session-secret
coeus-dev-csrf-secret
coeus-dev-local-seed-credential
coeus-dev-llm-provider-config
coeus-dev-object-storage-config
```

Generate local values:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Add a version without exposing it in shell history:

```powershell
$tmp = New-TemporaryFile
Set-Content -Path $tmp -NoNewline -Value "<SECRET_VALUE>"
gcloud secrets versions add coeus-dev-session-secret --data-file=$tmp --project <PROJECT_ID>
Remove-Item $tmp
```

Repeat for each secret. The local seed credential must not be the public
development default.

For `coeus-dev-database-url`, create a database user first in the GCP Console:

1. Go to **SQL > coeus-dev-postgres > Users**.
2. Add user `coeus_app`.
3. Generate a strong password in an approved work password vault.
4. Do not paste the password into chat, Markdown or shell history.

Then set the database URL secret to a Cloud SQL Unix socket URL:

```text
postgresql+asyncpg://coeus_app:<URL_ENCODED_DATABASE_PASSWORD>@/coeus?host=/cloudsql/<PROJECT_ID>:europe-west2:coeus-dev-postgres
```

URL-encode special characters in the password before adding the secret version.
Cloud SQL can back the current compatibility state table and the relational
Intelligence Store schema. Apply Alembic migrations before relying on a
persistent hosted database.

## Build And Push Bootstrap Images

```powershell
gcloud auth configure-docker europe-west2-docker.pkg.dev --quiet

cd C:\path\to\Coeus
$repo = "europe-west2-docker.pkg.dev/<PROJECT_ID>/coeus"

docker build -f infra/docker/api.Dockerfile -t "$repo/coeus-api:bootstrap" .
docker push "$repo/coeus-api:bootstrap"

docker build `
  --build-arg "VITE_API_BASE_URL=https://bootstrap.invalid" `
  -f infra/docker/web-prod.Dockerfile `
  -t "$repo/coeus-web:bootstrap" .
docker push "$repo/coeus-web:bootstrap"
```

## Apply The Full Dev Environment

```powershell
cd C:\path\to\Coeus\infra\gcp\environments\dev
terraform plan -out coeus-dev.tfplan
terraform apply coeus-dev.tfplan
terraform output
```

Copy the `web_service_url`, then set CORS:

```powershell
$webUrl = terraform output -raw web_service_url
$env:TF_VAR_allowed_cors_origins = "[`"$webUrl`"]"
terraform plan -out coeus-dev-cors.tfplan
terraform apply coeus-dev-cors.tfplan
```

## Validate The Dormant Reference In GitHub Actions

Run **Actions > Future GCP Migration Reference > Run workflow** only for an
authorised migration exercise, and select the required confirmation input.
The workflow validates Terraform, runs its migration-gate and single-writer
tests, and builds API and web images locally. It has no GCP authentication,
registry push, infrastructure mutation or deployment step. There is no
push-triggered or scheduled deployment path.

Do not create deployment variables or enable a protected deployment environment
until every ADR 0019 readiness gate passes and a separate supported deployment
workflow has been reviewed and authorised.

## Verify

```powershell
gcloud run services describe coeus-dev-api `
  --region europe-west2 `
  --project <PROJECT_ID> `
  --format="value(status.url)"

gcloud run services describe coeus-dev-web `
  --region europe-west2 `
  --project <PROJECT_ID> `
  --format="value(status.url)"
```

Open the web URL and sign in with the work-approved dev seed credential.

## Rollback

List recent revisions:

```powershell
gcloud run revisions list --service coeus-dev-api --region europe-west2 --project <PROJECT_ID>
gcloud run revisions list --service coeus-dev-web --region europe-west2 --project <PROJECT_ID>
```

Route traffic to a known-good revision:

```powershell
gcloud run services update-traffic coeus-dev-api `
  --region europe-west2 `
  --project <PROJECT_ID> `
  --to-revisions REVISION_NAME=100
```
