# Local First With GCP Reference Spec

## Goal

Keep Istari runnable on a developer machine without GCP while preserving detailed,
generic instructions for a future work-owned GCP deployment.

## Scope

- Local setup documentation must be the primary path.
- GCP documentation must use placeholders, not personal project or account
  details.
- Terraform examples must require project-specific values from private local
  variables, not committed defaults.
- The GCP scaffold must include every secret required by current runtime
  security checks.

## Non-Goals

- Applying Terraform against a live GCP project.
- Hosting persistent database repositories in GCP.
- Adding real GCS, Pub/Sub or cloud AI adapters beyond existing configuration.

## Acceptance Criteria

- `README.md` and `docs/SETUP.md` clearly state local running is supported and
  GCP is not required.
- GCP runbooks use placeholder project values only.
- Terraform dev variables do not default to a personal project ID, project
  number or image registry.
- Secret Manager placeholders include the non-default local seed credential used
  by dev Cloud Run startup.
