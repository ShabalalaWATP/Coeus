# ADR 0018: Retire Legacy Projects Workspaces

## Status

Accepted.

## Context

A former Projects/workspace feature added a separate navigation area, seed
workspace data, workspace-specific access policy and workspace detail routes.
The current product direction centres on requests, team queues, analyst/QC
workflow, ACG-governed Store access and search. Maintaining that separate
Projects surface created duplicated navigation and extra access-control paths
without a current owner workflow.

## Decision

Retire the legacy Projects feature:

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
- Do not keep active decoder shims for retired workspace fields. Local snapshots
  from earlier workspace builds must be reset or migrated outside the runtime.

## Consequences

- Users move between requests, queues, analyst/QC workspaces and the Store
  without a separate workspace area.
- Product visibility remains enforced by product RBAC, clearance, product
  status, draft rules and active ACG overlap.
- Existing local PostgreSQL schemas are cleaned by a migration that drops the
  old Store metadata column.
- Existing local JSON snapshots that still contain retired workspace payloads,
  permission values or ticket field names should be reset before running the
  current application.
- Future work can reintroduce a planning workspace only with a new spec, ADR,
  tests and clear user workflow.
