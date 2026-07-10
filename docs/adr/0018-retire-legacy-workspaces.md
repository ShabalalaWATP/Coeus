# ADR 0018: Remove Legacy Planning Workspaces

## Status

Accepted.

## Context

A former planning workspace feature added a separate navigation area, seed
workspace data, workspace-specific access policy and workspace detail routes.
The current product direction centres on requests, team queues, analyst/QC
workflow, ACG-governed Store access and search. Maintaining that separate
surface created duplicated navigation and extra access-control paths without a
current owner workflow.

## Decision

Remove the legacy planning workspace feature:

- Remove legacy workspace API routes, frontend routes, navigation items and admin
  shortcuts.
- Remove workspace domain records, seed data, services and response
  schemas.
- Remove old Store workspace metadata and search filters so the retired concept
  does not remain in the product contract.
- Remove the ticket-level suggested workspace name from intake and ticket
  responses.
- Rename ticket-level routing plan updates to workflow plan updates.
- Remove retired workspace permission enum strings from the active permission
  contract.
- Keep no active feature shims or retired workspace sanitisation in runtime
  persistence. Unknown retired records or permissions fail closed during decode.

## Consequences

- Users move between requests, queues, analyst/QC workspaces and the Store
  without a separate workspace area.
- Product visibility remains enforced by product RBAC, clearance, product
  status, draft rules and active ACG overlap.
- Existing PostgreSQL schemas and JSONB snapshots are cleaned by one-way
  migrations that drop old Store metadata and retired workspace payloads.
- Future work can reintroduce a planning workspace only with a new spec, ADR,
  tests and clear user workflow.
