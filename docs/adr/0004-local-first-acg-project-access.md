# ADR 0004: Local-first ACG And Project Access Model

## Status

Accepted.

## Context

Sprint 3 needs Access Control Groups, project workspace visibility and product access filtering before the database schema and migration phase. The implementation must establish the access-policy boundary now without coupling route handlers to temporary seed data.

## Decision

Use explicit local-first domain, repository and service boundaries:

- `SeedAccessRepository` owns synthetic ACGs, memberships, product summaries and project workspaces for local development.
- `AccessControlGroupService` owns ACG visibility, creation, updates and membership assignment.
- `ProductAccessPolicy` evaluates active user, RBAC, product status, clearance, draft visibility and ACG membership checks.
- `ProjectAccessPolicy` evaluates active user, project read permission, project membership and project ACG membership.
- `ProjectWorkspaceService` returns project views with product lists filtered through `ProductAccessPolicy`.
- `AccessDiagnosticsService` exposes explainable product access decisions for administrators.

FastAPI route handlers remain thin and only marshal request, response and authentication dependencies. Frontend route guards remain a user-experience layer; backend services and route dependencies remain authoritative.

## Consequences

- The future database adapter can replace the seed access repository without changing access-policy route handlers.
- Access decisions are unit-testable without HTTP or browser state.
- The local UI can exercise the required ACG and project flows before the persistence phase.
- The seed repository is not a substitute for migrations, indexes or durable audit storage.
- Additional caveat and releasability rules can be added inside `ProductAccessPolicy` without changing frontend route contracts.
