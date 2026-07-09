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
| Session theft via JavaScript or downgraded transport | Session ID is stored only in an HTTP-only SameSite cookie, route dependencies use the active app settings, and staging/prod startup requires secure cookies. |
| CSRF on logout or future state-changing auth actions | State-changing authenticated requests require `X-CSRF-Token`. |
| Username enumeration | Invalid usernames and invalid passwords return the same generic error and both paths run password verifier work. |
| Brute-force login attempts | Username-level lockout after repeated failures, source-level throttling, bounded attempt tracking and bounded audit retention. Saturated attempt stores fail closed instead of permitting new sources or usernames to bypass throttling. |
| Disabled user access | Disabled seed accounts are blocked before session creation. |
| Frontend-only access control bypass | Backend `require_permission` dependency protects administrative and audit endpoints. |
| Missing auth accountability | Login success, login failure and logout create audit events. |
| Password changes persist without audit evidence | Successful self-service password changes invalidate existing sessions, issue a fresh session and create `password_changed`. If that audit event cannot be recorded, the previous password, sessions and login-attempt state are restored. |
| Token persistence in browser local storage | Auth session and CSRF token are kept in React state; tests assert no token-like local storage entry. |
| Local seed user exposure | Application startup rejects the seed user repository outside `local` and `test` environments. |
| Privileged account change abuse | The admin user-management API requires `user:assign_role`, `user:disable` or `user:clearance` permissions per action, blocks self-modification and records audit events. |
| Credential reset secret leakage | Admin credential reset generates a temporary credential server-side, returns it once, never stores or audits the plaintext value, revokes target sessions and clears target login-attempt lockout state. |

## Open Risks

- Sessions persist when `COEUS_PERSISTENCE_PROVIDER=postgres` is enabled;
  memory mode remains throwaway for tests and isolated demos.
- Lockout is username-scoped and local-process scoped until distributed rate
  limiting is added, but in-process attempt and audit stores are bounded.
- Secure cookies are configurable and off by default for local HTTP development. Staging and production startup require `COEUS_SECURE_COOKIES=true`.
- Non-local environments require persistent user storage before startup because public seed users are local/test only.
- Admin user-management and credential reset are implemented for local/test seed users. Persistent production user storage remains required before non-local startup.
