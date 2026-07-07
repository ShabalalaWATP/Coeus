# Sprint 2 Spec: Auth, RBAC And App Shell

## Purpose

Add secure local-first authentication, server-side sessions, backend RBAC checks, role-driven navigation and authentication pages.

## Scope

- Secure login page with Coeus logo slot and private system notice.
- Generic authentication errors, locked account state and show/hide password control.
- Backend-driven current-user and permissions endpoint.
- Argon2id password hashing for seed users.
- Server-side session records and HTTP-only SameSite session cookies.
- CSRF validation for state-changing authenticated requests.
- Short-lived sessions and session rotation endpoint.
- Account lockout after repeated failed attempts.
- Disabled users blocked from login.
- Auth audit events for login success, login failure and logout.
- Backend RBAC dependency and protected admin/audit endpoints.
- Role-driven navigation based on backend permissions.
- `/login`, `/forbidden` and `/session-expired` routes.
- Branch protection documentation for the target GitHub repository.

## Non-goals

- Persistent database user tables. The Sprint 2 user repository is a local seed adapter behind a repository boundary.
- MFA. The implementation plan explicitly keeps MFA out of scope for the target air-gapped end state.
- ACG enforcement. That starts in Sprint 3.
- Admin user creation, disable and role assignment UI. The backend permission model is prepared for it, but the management surface is later work.

## Local Seed Users

All seed accounts use synthetic `example.test` usernames and the mock local credential `CoeusLocal1!`.

| Username | Role | Default route |
|---|---|---|
| `admin@example.test` | Administrator | `/admin/overview` |
| `user@example.test` | User | `/app/requests` |
| `rfa.manager@example.test` | Request for Assessment Manager | `/rfa/queue` |
| `rfa.team@example.test` | Request for Assessment Team Member | `/rfa/products` |
| `collection.manager@example.test` | Collection Manager | `/collection/queue` |
| `collection.team@example.test` | Collection Team Member | `/collection/products` |
| `analyst@example.test` | Intelligence Analyst | `/analyst/workbench` |
| `qc.manager@example.test` | Quality Control Manager | `/qc/queue` |
| `store.manager@example.test` | Intelligence Store Manager | `/store` |
| `disabled@example.test` | User, disabled | blocked |

These are mock development credentials, not production credentials.

## Acceptance Criteria

- Valid credentials create an HTTP-only SameSite session cookie.
- Invalid usernames and invalid passwords return the same generic error.
- Repeated login failures trigger lockout.
- Disabled users cannot log in.
- Logout requires CSRF and revokes the session.
- Expired sessions return `401` with `session_expired`.
- Direct API calls without permission return `403`.
- Frontend direct unauthorised routes show `/forbidden`.
- Frontend expired sessions show `/session-expired`.
- No auth token is stored in local storage.
- Each role receives navigation from backend permissions.

## Verification

- Backend: `uv run ruff check src tests`, `uv run mypy src` and `uv run pytest` passed from `apps/api`.
- Frontend: `pnpm format:check`, `pnpm --filter @coeus/web lint`, `pnpm --filter @coeus/web typecheck`, `pnpm --filter @coeus/web test` and `pnpm --filter @coeus/web build` passed.
- Browser: `pnpm --filter @coeus/web test:e2e` passed, and a live local browser smoke verified admin login, user 403 handling and no auth token in local storage.
- Security: `uv run bandit -r src`, `uv run pip-audit`, `uv run semgrep scan --config auto --no-git-ignore src` and `pnpm --filter @coeus/web audit --prod` passed.
- Infrastructure: `docker compose config` passed.
