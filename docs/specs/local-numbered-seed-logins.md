# Local Numbered Seed Logins

## Purpose

Provide memorable usernames for local multi-role evaluation without changing
the canonical synthetic identities used by tests, seed specifications and
internal demo relationships.

## Scope

The Docker Compose API enables `COEUS_LOCAL_NUMBERED_SEED_USERNAMES=true` and
sets `COEUS_LOCAL_SEED_CREDENTIAL=admin`. The feature is rejected unless the
runtime environment is `local`.

## Behaviour

- The 16 canonical seed identities map in specification order to `admin1`
  through `admin16`.
- All 16 accounts receive the temporary password `admin` during the first
  migration to the numbered login profile. `admin16` remains disabled.
- Migration preserves user IDs, display names, roles, permissions derived from
  those roles, clearance and active state. Team, ticket and access-group links
  therefore keep their existing user-ID references.
- Credential versions increase during the migration, invalidating sessions
  issued before the username or password change.
- The username, credential updates and migration marker are persisted together
  in the users state payload. A later restart does not reset a password changed
  by the user.
- Public authentication lookup is exact. Canonical `example.test` names are not
  login aliases for numbered accounts and cannot create a second lockout key.
- Browser login validation accepts both numbered and canonical usernames using
  the API's 3 to 254 character boundary rather than requiring an email address.
- The Compose web client derives the API hostname from the browser hostname, so
  sessions remain same-site through both `localhost` and `127.0.0.1` entry URLs.
- Canonical and numbered forms are both reserved from self-registration while
  the numbered profile is active.
- Internal demo seed construction uses an explicit canonical-identity resolver;
  user-facing username lookup remains exact.
- Startup fails closed if an existing account conflicts with a target numbered
  username.

## Acceptance Evidence

Automated tests cover identity and authority preservation, one-time password
migration, canonical-alias rejection, prior-session invalidation, collision
failure, disabled-user rejection, team profile creation and hosted-environment
rejection.

## Security Boundary

The shared `admin` password is deliberately weak. It is for a loopback-bound,
synthetic local demonstration only and must never be reused in a shared, dev,
staging or production deployment. See the
[auth threat model](../threat-model/auth-rbac-sessions.md) and
[local development runbook](../runbooks/local-development.md).
