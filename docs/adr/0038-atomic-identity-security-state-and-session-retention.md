# ADR 0038: Atomic Identity Security State And Session Retention

## Status

Accepted on 18 July 2026.

## Context

Password change currently carries a complete `UserAccount` across password
verification and hashing, then saves that stale object. A concurrent
administrator can successfully disable or otherwise restrict the account and
have that decision overwritten by the later password save. Session creation
also retains abandoned sessions without an explicit server-owned bound.

Credential versions prevent stale sessions from authenticating, but they do
not make a stale whole-account save safe. This ADR extends the monotonic
revocation objective in ADR 0028.

## Decision

1. Identity repositories expose current-state conditional mutations for every
   security-sensitive account change.
2. Password changes update credential-owned fields only and confirm all
   dependent session and audit work while the expected account state remains
   current.
3. Administrative status, role, clearance and credential changes use the same
   conflict contract. No security flow compensates with an unconditional save
   of an old whole-account snapshot.
4. Session admission atomically prunes expired records and applies limits of
   five retained sessions per user and 1,000 per local deployment by default.
5. Per-user overflow evicts the oldest session for that user. Global saturation
   rejects the new session and never evicts another user's valid session.
6. Memory and PostgreSQL-backed operation share the same conflict, capacity,
   rollback and audit behaviour.
7. Capacity, conflict and pruning outcomes use bounded metrics and audit
   metadata without session identifiers.

## Consequences

- A password change may return a conflict when another security decision wins.
- Users keep a bounded number of concurrent devices without needing to present
  abandoned cookies for cleanup.
- Repository APIs become narrower and more explicit, while persistence and
  failure-path tests become more substantial.
- Individually keyed relational sessions remain a future optimisation. The
  bounded aggregate is acceptable only for the current local deployment and
  must be replaced before shared or high-scale deployment.

## Rejected Alternatives

- Re-reading before an unconditional save: another mutation can occur after the
  read and before the save.
- Relying only on credential versions: the race overwrites active state, roles
  and clearance as well as credentials.
- Unlimited expiry-only retention: abandoned cookies are never presented, so
  presentation-time expiry does not bound storage.
- Evicting another user's session at global capacity: an attacker could turn
  login attempts into cross-user session revocation.
