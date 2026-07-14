# ADR 0028: Monotonic Credential And Session Revocation

## Status

Accepted for Sprint 17, 2026-07-14.

## Context

Session rotation previously read an active session and replaced it in separate
repository operations. Concurrent logout or password change could revoke the
source between those operations and the rotation could recreate authenticated
state. A related interleaving allowed a login that had verified an old password
to issue a session after a concurrent password change.

Logout also has an asymmetric failure mode. Restoring a session when the logout
audit sink fails preserves audit atomicity, but it can re-enable a credential
the user explicitly tried to revoke. The browser cannot safely treat a failed
logout response as confirmation that the server session is gone.

## Decision

- Session rotation uses one repository compare-and-swap operation. The source
  session must still exist, belong to the same user and have a non-colliding
  replacement ID. One concurrent replacement can win.
- User records carry a monotonically increasing `credential_version`. Sessions
  capture that version and validation rejects mismatches. Password changes and
  administrative credential resets increment it. Legacy persisted records
  decode as version 0.
- Login rechecks the stored credential version and verifier after issuing its
  candidate session. A concurrent credential change deletes or invalidates the
  candidate before it can authorise a later request.
- Logout revocation is security-first. Once the session is deleted it is not
  restored if audit recording fails. The HTTP request fails, so no successful
  unaudited logout is reported, while the revoked credential stays revoked.
- The web client immediately hides protected state, retains only the CSRF value
  needed for retry, and enters a persistent unconfirmed state until the backend
  proves logout or session absence. Logout transitions are deduplicated and
  broadcast to other tabs. The persistent marker contains no credential or user
  identifier.

## Consequences

- Revocation is monotonic across persisted local state and process restarts.
- Losing rotation and logout races return a generic authentication failure.
- An audit outage can produce a revoked session without a logout audit event.
  This is an explicit fail-secure trade-off and requires operational alerting on
  audit failures.
- The compare-and-swap repository is process-local in the current adapter.
  A hosted multi-process adapter must implement the same invariant in one
  durable transaction and retain credential-version checks.
- Logout revokes the presented session only. Password change and administrative
  reset are the supported session-family revocation operations.
- Rolling back to code that ignores credential versions requires draining
  sessions or forced reauthentication first. Version-0 decode compatibility is
  for migration, not permission to accept post-increment sessions in old code.
