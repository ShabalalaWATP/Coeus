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
| Missing auth accountability | Login success, login failure and logout create audit events. Login restores its prior session and attempt state if its audit event fails. Logout is deliberately fail-secure: an audit failure fails the request but never restores the revoked session. |
| Password changes persist without audit evidence | Successful self-service password changes invalidate existing sessions, issue a fresh session and create `password_changed`. If that audit event cannot be recorded, the previous password, sessions and login-attempt state are restored. |
| A password change restores a concurrent disable, role or clearance decision | Password changes and administrative identity mutations use expected-current-state writes, confirm the resulting account before session issue and conditionally compensate only their own exact saved state. A losing concurrent operation returns a conflict instead of restoring a stale whole account. |
| Session rotation races logout or password change | Session replacement is one compare-and-swap operation. Credential versions are captured in sessions and advanced on password change or reset, so a stale rotation or old-password login cannot survive revocation. |
| An interactive request outlives its initiating session | Chat, active-work and RFI final commits require the exact session that initiated the request to remain active. Another session for the same user cannot preserve the in-flight operation. Workflow and submission paths lock mutable authority in the canonical users, sessions, access, teams, products, ticket order. |
| Abandoned cookies grow durable session state without bound | Session issue prunes expiry, retains at most five sessions per user and rejects new sessions when the 1,000-session local deployment ceiling is full. Per-user overflow evicts only that user's oldest session. Restore also normalises legacy over-limit state. |
| Concurrent password work exhausts memory or CPU | Login, registration and administrative credential operations share one bounded Argon2 admission pool and fail fast with a generic `429` when full. |
| Failed logout appears complete or leaves protected browser state visible | Logout immediately clears protected query state, persists and broadcasts a non-secret pending marker, blocks public and protected routes, deduplicates requests and refreshes CSRF privately for retry. Only success or backend `401` clears the marker. |
| Token persistence in browser local storage | Auth session and CSRF token are kept in React state; tests assert no token-like local storage entry. |
| The browser misses a forced password reset because its session type drifts from the API | The frontend auth client derives its response shape from generated OpenAPI types and reads `passwordResetRequired` from the returned user profile. Protected routing and password-change-required events update that same field. |
| Local seed user exposure | Application startup rejects the seed user repository outside `local` and `test` environments. |
| Seed identity refresh duplicates accounts or breaks active references | Startup renames only recognised legacy synthetic usernames, preserves the existing user ID and credential state, and reconciles before adding missing seed users. Sessions and team links therefore retain their user-ID reference. |
| Seed refresh overwrites local administrator changes | Display names update only when they still equal a recognised legacy seed value; edited values remain authoritative. Profile reconciliation applies the same exact-match rule. |
| Privileged account change abuse or mid-request revocation | The admin user-management API requires `user:assign_role`, `user:disable` or `user:clearance` per action and blocks self-modification. Role, status and clearance changes atomically compare the exact current actor and target, confirm the required live permission, apply target and session effects, and record audit evidence under one repository authority boundary. |
| Credential reset secret leakage | Admin credential reset generates a temporary credential server-side, returns it once, never stores or audits the plaintext value, revokes target sessions and clears target login-attempt lockout state. |

## Open Risks

- Sessions persist when `COEUS_PERSISTENCE_PROVIDER=postgres` is enabled;
  memory mode remains throwaway for tests and isolated demos.
- Lockout is username-scoped and local-process scoped until distributed rate
  limiting is added, but in-process attempt and audit stores are bounded.
- Secure cookies are configurable and off by default for local HTTP development. Staging and production startup require `COEUS_SECURE_COOKIES=true`.
- Argon2 capacity is process-local. Worker or replica counts multiply the total
  effective capacity, so hosted deployment sizing must preserve the documented
  aggregate memory budget.
- Non-local environments require persistent user storage before startup because public seed users are local/test only.
- Admin user-management and credential reset are implemented for local/test seed users. Persistent production user storage remains required before non-local startup.
