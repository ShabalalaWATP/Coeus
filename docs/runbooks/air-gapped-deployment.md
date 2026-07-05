# Air-Gapped Deployment Runbook

## Purpose

This runbook describes how to package Coeus for a restricted or disconnected
environment. It is a preparation guide, not a production accreditation.

## Package Contents

Prepare these artifacts from a clean, reviewed commit:

- source archive from the exact Git SHA
- API container image
- web container image
- CycloneDX SBOM
- Trivy image scan reports
- Checkov Terraform report
- CodeQL and Semgrep summaries
- ZAP baseline report for the local web target
- signed release note with the Git SHA, build time and scanner versions

Do not include `.env`, Terraform state, GCP credentials, service account keys,
database dumps, browser screenshots or real intelligence content.

## Build Steps

```powershell
git status --short --branch
pnpm install --frozen-lockfile
uv sync --project apps/api --frozen --all-groups
docker build -f infra/docker/api.Dockerfile -t coeus-api:<git-sha> .
docker build -f infra/docker/web-prod.Dockerfile -t coeus-web:<git-sha> .
```

Export images for transfer:

```powershell
docker save coeus-api:<git-sha> -o coeus-api-<git-sha>.tar
docker save coeus-web:<git-sha> -o coeus-web-<git-sha>.tar
```

## Verification Before Transfer

Run the normal local gates first:

```powershell
uv run --directory apps/api pytest
uv run --directory apps/api bandit -r src
uv run --directory apps/api pip-audit
pnpm --filter @coeus/web lint
pnpm --filter @coeus/web test
pnpm --filter @coeus/web build
pnpm line-limit
```

Run security packaging checks:

```powershell
gitleaks detect --source . --redact --verbose
checkov -d infra/gcp --framework terraform
trivy image --severity HIGH,CRITICAL coeus-api:<git-sha>
trivy image --severity HIGH,CRITICAL coeus-web:<git-sha>
syft . -o cyclonedx-json=coeus-sbom.cdx.json
```

Use the GitHub Actions artifacts when local scanner binaries are not available.

## Restricted Environment Notes

- Configure runtime secrets inside the target environment, never in the image.
- Use internal registries and pinned image digests after import.
- Disable external LLM providers unless an approved internal endpoint exists.
- Keep seed users limited to local or explicitly approved dev environments.
- Recreate SBOM and scan evidence after any rebuild inside the restricted
  environment.
- Record the imported image digests and the source Git SHA in the deployment
  log.
