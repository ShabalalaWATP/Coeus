# ADR 0004: Local-first ACG And Product Access Model

## Status

Superseded for project workspaces by ADR 0018. The ACG and product access parts remain accepted.

## Context

Sprint 3 needed Access Control Groups, project workspace visibility and product access filtering before the database schema and migration phase. The implementation had to establish the access-policy boundary without coupling route handlers to temporary seed data.

## Decision

Use explicit local-first domain, repository and service boundaries:

- `SeedAccessRepository` owns synthetic ACGs, memberships and product summaries for local development.
- `AccessControlGroupService` owns ACG visibility, creation, updates and membership assignment.
- `ProductAccessPolicy` evaluates active user, RBAC, product status, clearance, draft visibility and ACG membership checks.
- `AccessDiagnosticsService` exposes explainable product access decisions for administrators.

FastAPI route handlers remain thin and only marshal request, response and authentication dependencies. Frontend route guards remain a user-experience layer; backend services and route dependencies remain authoritative.

## Consequences

- The future database adapter can replace the seed access repository without changing access-policy route handlers.
- Access decisions are unit-testable without HTTP or browser state.
- The local UI can exercise the required ACG and product access flows before the persistence phase.
- The seed repository is not a substitute for migrations, indexes or durable audit storage.
- Additional caveat and releasability rules can be added inside `ProductAccessPolicy` without changing frontend route contracts.
