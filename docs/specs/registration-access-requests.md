# Registration Access Requests

## Goal

Allow prospective users to request an Istari account from the login splash
page. Requests are reviewed by administrators, who approve or reject them.
Approved requests become active `User` accounts.

## Behaviour

- `POST /api/v1/auth/register` accepts `username` (email format),
  `displayName`, optional `justification` and `password` (minimum 12
  characters). It always answers `202 {"status": "pending"}` for valid
  payloads so responses do not reveal whether an account or pending request
  already exists.
- Duplicate pending usernames and usernames that already belong to accounts
  are accepted generically but not stored again.
- Submissions beyond `registration_max_pending` (default 500) return `429`
  to bound memory use.
- Passwords are hashed with Argon2 at submission time; plaintext is never
  stored and hashes are never returned by any endpoint.
- `GET /api/v1/admin/registrations` lists pending requests and requires the
  `user:create` permission.
- `POST /api/v1/admin/registrations/{id}/approve` and
  `.../reject` require a CSRF-validated session plus `user:create`. Approval
  creates an active account with the `User` role and clearance level 1.
  Rejection requires a short reason. Both decisions are audit logged.
- If a username becomes taken between submission and approval, approval
  marks the request rejected and returns `409 username_taken` so the
  repository never overwrites an existing account.

## Out of scope

- Email verification and notification of applicants.
- Role selection at registration time; administrators assign further roles
  through future user management features.
