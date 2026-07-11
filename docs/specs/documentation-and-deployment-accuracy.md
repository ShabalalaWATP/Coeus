# Documentation and deployment accuracy

## Purpose

Keep the active documentation aligned with the application at `main`, preserve
local development as the supported default, and describe cloud migration without
claiming that dormant reference infrastructure is deployable today.

## Support matrix

| Target                                 | Current status    | Supported use                                      |
| -------------------------------------- | ----------------- | -------------------------------------------------- |
| Local processes plus Docker PostgreSQL | Supported         | Development, demos and local multi-role evaluation |
| Full Docker Compose stack              | Supported locally | Container-parity development and demos             |
| GCP Cloud Run reference                | Blocked reference | Migration planning only                            |
| Kubernetes                             | Not implemented   | Migration planning only                            |

## Required outcomes

- Local setup commands load the documented root `.env` and retain the current
  PostgreSQL-first workflow.
- Docker documentation distinguishes the used services from MinIO scaffolding.
- Active screenshots represent the current navigation, labels and workflows.
- User documentation covers the implemented local account-management lifecycle
  without presenting it as a production identity platform.
- GCP documentation names every current blocker and removes instructions that
  could bypass the readiness gate or build a web client against a dummy API URL.
- Kubernetes documentation explains the reusable container boundaries, a
  constrained single-replica evaluation topology and production readiness gates.
- Historical specifications remain historical; active guides and status records
  identify superseded claims where necessary.

## Non-goals

- Deploying to GCP or Kubernetes.
- Adding Kubernetes manifests or a Helm chart.
- Enabling multiple API writers.
- Replacing local PostgreSQL, local object storage or offline providers.

## Verification

- All Markdown links and embedded image paths resolve.
- `docker compose config --quiet` passes.
- Documentation commands match current scripts, settings and container files.
- Formatting, line-limit and relevant repository checks remain green.
