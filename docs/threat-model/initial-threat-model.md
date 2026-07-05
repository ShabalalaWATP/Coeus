# Initial Threat Model

## Scope

Sprint 1 covers repository structure, API skeleton, web shell, CI and local development services.

## Assets

- Source code and CI configuration.
- Local PostgreSQL data.
- Local MinIO object data.
- OpenAPI schema.
- Future user sessions and product metadata.

## Trust Boundaries

- Browser to FastAPI API.
- API to PostgreSQL.
- API to local or cloud object storage.
- CI runners to package registries.
- Public repository to local developer environments.

## Initial Threats And Controls

| Threat | Control in Sprint 1 |
|---|---|
| Secret leakage into a public repository | `.gitignore`, `.env.example`, repository safety documentation, CI dependency hygiene. |
| Missing request traceability | API request ID middleware and response header. |
| Unsafe browser defaults | Security headers on API responses. |
| Unavailable database hidden by shallow health checks | Readiness endpoint performs a database check. |
| Low-quality baseline accepted too early | Backend and frontend coverage gates set to 95 percent line and branch coverage. |
| Supply-chain drift | Dependabot configuration, CI lockfile usage, pnpm release-age cooldown and pnpm trust policy. |

## Open Risks

- Authentication, session security, RBAC and ACG enforcement start in later sprints.
- MinIO image is currently used for local development only and should be pinned before release hardening.
- Full seed insertion waits for database schema implementation.
