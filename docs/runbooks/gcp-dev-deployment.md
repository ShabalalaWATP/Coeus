# GCP Reference Deployment and Migration Guide

## Current status

Istari runs locally by default. The GCP files are a dormant reference for a
future work-owned development environment, not a supported deployment. Do not
apply the Terraform or push bootstrap images today.

The reference models:

- Cloud Run services for the API and static web container;
- Artifact Registry, Cloud SQL PostgreSQL, Cloud Storage, Pub/Sub, KMS, Secret
  Manager and Workload Identity Federation.

The current GitHub workflow validates Terraform and builds images locally only.
It has no GCP authentication, registry push, infrastructure mutation or traffic
deployment step.

## Why deployment is blocked

All of these conditions must be resolved before the reference can be enabled:

1. The runtime rejects `COEUS_OBJECT_STORAGE_PROVIDER=gcs`; no GCS adapter exists.
2. The runtime rejects `COEUS_PUBSUB_ENABLED=true`; no worker adapter exists.
3. The API uses whole-namespace, single-writer state and must remain one instance.
4. Hosted identity lifecycle, backup/restore, audit export, monitoring and
   incident-response procedures are incomplete.
5. Terraform does not currently inject the required hosted asset-token secret.
6. The web API origin is compiled into the Vite bundle. The old bootstrap command
   used `https://bootstrap.invalid`, which cannot produce a working UI.
7. A full apply is stopped by `migration_adapters_ready=false`. Targeted applies
   can bypass the dependency for resource-shell modules, so they are prohibited.
8. There is no reviewed migration job that can reach Cloud SQL and run Alembic.

## Values required after readiness approval

Use an authorised work project and approved secret manager:

```text
PROJECT_ID=<work-gcp-project-id>
PROJECT_NUMBER=<numeric-project-number>
REGION=europe-west2
GITHUB_REPOSITORY=<github-owner>/<repository>
```

Project IDs, numbers, region and service names are identifiers. Never commit or
share service-account keys, database passwords, session/CSRF/asset-token secrets,
API keys, Terraform state or plans.

## Required implementation work

Before changing the readiness flag:

- implement GCS product-asset storage with the same authorisation, streaming,
  token and rollback guarantees as local storage;
- implement Pub/Sub publishing and worker idempotency, retry and dead-letter
  behaviour, or keep Pub/Sub disabled and remove unused resources;
- replace or formally constrain single-writer state; keep Cloud Run API maximum
  instances at one until distributed invariants are implemented;
- add persistent production user storage or an approved identity provider;
- add `COEUS_ASSET_TOKEN_SECRET` to Secret Manager and the API mapping;
- create a Cloud Run Job or other private migration runner for
  `alembic upgrade head`;
- add database/object backup, restore tests, retained audit export, monitoring,
  alerts and rollback;
- make every cloud-creating Terraform module depend on the readiness gate so
  `-target` cannot bypass it;
- independently review the threat model and Terraform plan.

## Migration order after every gate passes

### 1. Validate tools and identity

Install and verify `gcloud`, Terraform and Docker. Use Workload Identity
Federation for CI; do not create long-lived service-account keys.

```powershell
gcloud auth application-default login
gcloud config set project <PROJECT_ID>
gcloud projects describe <PROJECT_ID> --format="value(projectNumber)"
terraform -chdir=infra/gcp/environments/dev init
terraform -chdir=infra/gcp/environments/dev fmt -check -recursive
terraform -chdir=infra/gcp/environments/dev validate
terraform -chdir=infra/gcp/environments/dev test
```

### 2. Review one complete infrastructure plan

Create a private `terraform.tfvars` from the example. Use immutable image
references, enable Cloud SQL deletion protection outside disposable development,
and set the final HTTPS web origin in `allowed_cors_origins`. Do not use targeted
apply. Review a complete plan before any apply.

### 3. Provision data and secret services

After formal readiness approval, apply the reviewed configuration to create the
resource shell. Create a least-privilege Cloud SQL application user. Add secret
versions for database URL, session, CSRF and asset-token secrets plus any selected
provider credentials. Never store secret values in Terraform variables.

### 4. Build and publish the API image

```powershell
$repo = "europe-west2-docker.pkg.dev/<PROJECT_ID>/coeus"
gcloud auth configure-docker europe-west2-docker.pkg.dev --quiet
docker build -f infra/docker/api.Dockerfile -t "$repo/coeus-api:<GIT_SHA>" .
docker push "$repo/coeus-api:<GIT_SHA>"
```

Run the approved migration job against Cloud SQL before routing traffic to the
new API revision. Deploy the API at zero traffic, verify live/readiness endpoints,
then obtain its final HTTPS URL.

### 5. Build the web image with the real API URL

`VITE_API_BASE_URL` is build-time configuration. Build only after the API URL is
known:

```powershell
$apiUrl = "https://<actual-api-service-url>"
docker build --build-arg "VITE_API_BASE_URL=$apiUrl" `
  -f infra/docker/web-prod.Dockerfile `
  -t "$repo/coeus-web:<GIT_SHA>" .
docker push "$repo/coeus-web:<GIT_SHA>"
```

Update the reviewed Terraform image values, plan again and deploy the web
revision. Confirm API CORS contains the final web URL and secure cookies are on.

### 6. Validate before admitting users

- exercise sign-in, CSRF, request creation, routing, assignment, QC and asset
  upload/download using synthetic data;
- verify object-level access, ACG and clearance enforcement;
- verify logs contain no secrets and audit export is retained;
- restore a database and object backup in an isolated environment;
- exercise revision rollback and confirm migrations are compatible;
- keep the API at one instance until distributed-state work is complete.

## Rollback

Cloud Run can route traffic to a previous known-good revision, but application
rollback also depends on database and object-schema compatibility. Record the
image digests, migration version and Terraform plan for every release. Never roll
back code across a destructive migration without an approved recovery plan.

## GitHub workflow boundary

**Future GCP Migration Reference** remains validation-only. A future deployment
workflow must use a protected GitHub Environment, least-privilege Workload
Identity Federation, immutable image digests, approvals, migration and smoke
gates, and an explicit rollback path. Enabling that workflow is a separate
security-reviewed change.
