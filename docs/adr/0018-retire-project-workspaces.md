# ADR 0018: Retire Project Workspaces

## Status

Accepted.

## Context

The project workspace feature added an extra `/projects` navigation area, seed
workspace data, project-specific access policy and project detail routes. The
current product direction centres on requests, team queues, analyst/QC
workflow, ACG-governed Store access and search. Maintaining project workspaces
created duplicated navigation and extra access-control paths without a current
owner workflow.

## Decision

Retire the project workspace feature:

- Remove `/projects` API routes, frontend routes, navigation items and admin
  shortcuts.
- Remove project workspace domain records, seed data, services and response
  schemas.
- Remove Store `projectId` metadata and search filters so the retired Projects
  concept does not remain in the product contract.
- Keep retired project permission enum strings only so older local state
  snapshots can decode safely.
- Keep ticket-level routing plan updates as workflow artefacts, not workspace
  records.

## Consequences

- Users move between requests, queues, analyst/QC workspaces and the Store
  without a separate Projects area.
- Product visibility remains enforced by product RBAC, clearance, product
  status, draft rules and active ACG overlap.
- Existing local state files that still contain `projects` payloads are ignored
  by the access snapshot loader.
- Existing local Store snapshots that contain product `project_id` metadata are
  decoded with that field ignored; local PostgreSQL migrations drop the old
  Store column.
- Future work can reintroduce a planning workspace only with a new spec, ADR,
  tests and clear user workflow.
