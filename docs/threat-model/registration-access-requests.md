# Threat Model: Registration Access Requests

Scope: the public `POST /api/v1/auth/register` endpoint and the
administrator review endpoints under `/api/v1/admin/registrations`.

## Assets

- Requested credentials (Argon2 hash only, held in memory until decided).
- The seed user store, which approval writes into.
- Administrator review workflow integrity.

## Threats and mitigations

- Account enumeration through registration responses: valid submissions
  always return the same generic `202 pending` body whether or not the
  username exists as an account or pending request.
- Credential exposure: passwords are hashed with Argon2 immediately on
  submission; the plaintext is never persisted, logged or echoed, and list
  endpoints exclude the hash.
- Memory exhaustion through unauthenticated submissions: pending requests
  are capped by `registration_max_pending`; excess submissions receive
  `429` and an audit event.
- Argon2 CPU or memory exhaustion: registration hash work shares the bounded
  password-work semaphore used by login and administration. A saturated pool
  fails before a second Argon2 call and releases the registration reservation.
- Privilege escalation through approval: approval always grants only the
  `User` role at clearance level 1; role changes remain an administrator
  action outside this flow. Review endpoints require `user:create`, and
  mutating endpoints additionally require the CSRF header bound to the
  session.
- Account overwrite on approval: if the username became taken after
  submission, approval rejects the request with `409 username_taken`
  instead of overwriting the account entry.
- Auditability: submission, throttling, duplicates, approval and rejection
  all raise audit events; decision events record the acting administrator.
- Once a request is approved or rejected, its password verifier is removed
  from registration persistence. Approved accounts retain only their account
  verifier; rejected requests retain no reusable credential material.

## Residual risks

- No email ownership verification: an applicant can request any address.
  Administrators must verify identity out of band before approving.
- In-memory storage: pending requests are lost on restart, consistent with
  the local-first seed architecture.
- The Argon2 limiter is per process. Hosted worker counts must be included in
  the aggregate memory budget.
