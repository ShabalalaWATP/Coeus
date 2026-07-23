# Documentation and deployment accuracy

## Purpose

Keep the active documentation aligned with the application at `main`, preserve
local development as the supported default, and describe cloud migration without
claiming that dormant reference infrastructure is deployable today.

Companion records: [documentation maintenance](../development/documentation-maintenance.md),
[air-gapped deployment](../runbooks/air-gapped-deployment.md) and the
[security-hardening threat model](../threat-model/security-hardening.md).

## Support matrix

| Target                                 | Current status    | Supported use                                      |
| -------------------------------------- | ----------------- | -------------------------------------------------- |
| Local processes plus Docker PostgreSQL | Supported         | Development, demos and local multi-role evaluation |
| Full Docker Compose stack              | Supported locally | Container-parity development and demos             |
| GCP Cloud Run reference                | Blocked reference | Migration planning only                            |
| Kubernetes                             | Not implemented   | Migration planning only                            |

## Required outcomes

- The documentation index identifies which records describe current behaviour,
  which preserve historical decisions or evidence, and where release status is
  maintained.
- Every tracked Markdown file participates in the local-link and GitHub-style
  heading-anchor check, including component and infrastructure READMEs.
- Specifications, ADRs and threat models have complete linked indexes. Material
  changes add bidirectional companion links between their applicable records.
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

- All tracked Markdown links, embedded image paths and local heading anchors
  resolve.
- Current guides, implementation trackers and dated evidence do not make
  contradictory support, routing or release-readiness claims.
- `docker compose config --quiet` passes.
- Documentation commands match current scripts, settings and container files.
- Formatting, line-limit and relevant repository checks remain green.

## Deep-audit evidence, 23 July 2026

The repository-wide audit checked 184 Git-known Markdown files against shipped
routes, configuration, persistence schemas, scripts and current security
evidence. It established the lifecycle and cross-linking rules in the
[documentation maintenance guide](../development/documentation-maintenance.md),
added complete indexes for specifications, ADRs and threat models, corrected
the supported persistence and reset descriptions, and aligned current delivery
status with the integrated `0cde7010` security-remediation revision. The
air-gapped packaging review also isolated exact-SHA build inputs, bound SBOMs to
the transferred image archives and made nested transfer evidence fail closed.
