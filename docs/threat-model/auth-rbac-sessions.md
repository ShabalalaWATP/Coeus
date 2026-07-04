# Auth, RBAC And Sessions Threat Model

## Scope

Sprint 2 authentication, sessions, RBAC, audit events and frontend auth routes.

## Assets

- User accounts and role assignments.
- Session IDs and CSRF tokens.
- Audit events.
- Backend permissions and protected endpoints.

## Trust Boundaries

- Browser to FastAPI auth endpoints.
- Frontend route guards to backend RBAC enforcement.
- Local seed repository to future database-backed user repository.

## Threats And Controls

| Threat | Control |
|---|---|
| Password disclosure | Passwords are hashed with Argon2id. No plaintext credential is stored in user records. |
| Session theft via JavaScript | Session ID is stored only in an HTTP-only SameSite cookie. |
| CSRF on logout or future state-changing auth actions | State-changing authenticated requests require `X-CSRF-Token`. |
| Username enumeration | Invalid usernames and invalid passwords return the same generic error. |
| Brute-force login attempts | Username-level lockout after repeated failures. |
| Disabled user access | Disabled seed accounts are blocked before session creation. |
| Frontend-only access control bypass | Backend `require_permission` dependency protects administrative and audit endpoints. |
| Missing auth accountability | Login success, login failure and logout create audit events. |
| Token persistence in browser local storage | Auth session and CSRF token are kept in React state; tests assert no token-like local storage entry. |

## Open Risks

- Sessions are in-memory until the database schema and persistence layer are implemented.
- Lockout is username-scoped and local-process scoped until persistence and distributed rate limiting are added.
- Secure cookies are configurable and off by default for local HTTP development. Production must enable `COEUS_SECURE_COOKIES=true`.
- Admin user-management UI is not implemented in Sprint 2.
- Admin password reset is not implemented in Sprint 2. It must be delivered with persistent user management rather than added to the temporary seed repository.
