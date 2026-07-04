# ADR 0003: Local-first Auth And Session Boundaries

## Status

Accepted.

## Context

Sprint 2 needs authentication, sessions, RBAC and seed users before the database schema is introduced. The implementation must not add production shortcuts that bypass backend checks.

## Decision

Use explicit service and repository boundaries:

- `SeedUserRepository` provides synthetic local users for Sprint 2.
- `SessionRepository` stores opaque server-side session records.
- `LoginAttemptRepository` tracks username-level lockout.
- `AuthService` owns login, logout, session validation, CSRF validation, session rotation and permission checks.
- FastAPI routes only handle request/response marshalling and cookie operations.

Passwords are hashed with Argon2id at startup from the mock local seed credential. Authentication uses opaque HTTP-only SameSite cookies. CSRF tokens are returned to the frontend session context and must be sent as `X-CSRF-Token` on state-changing authenticated requests.

## Consequences

- The database adapter can replace the seed repository without changing route handlers.
- Backend RBAC is testable independently of the frontend.
- Frontend route guards improve user experience but do not become the authority for access.
- The mock seed credential is public-repository safe but must never be used outside local development.
