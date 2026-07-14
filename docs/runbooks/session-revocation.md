# Session Revocation And Recovery

## Security Contract

- User and session records carry `credential_version`. Legacy records decode as
  version 0. Password change and administrative credential reset increment the
  user version; every older session becomes invalid even if a concurrent
  operation retained its record.
- Session rotation consumes the presented session with compare-and-swap. A
  concurrent logout, password change or second rotation can leave only one
  authorised successor.
- Logout revokes only the presented session. It is not a session-family logout.
  Password change or administrative reset remains the operation that revokes
  every session for the user.
- Logout audit failure never restores the deleted session. The request fails so
  the browser must confirm absence or retry, while authority stays revoked.

## Browser Recovery

At sign-out start the web client clears protected query state, hides the session
and writes `coeus.logout.pending` to browser storage. The marker contains only
`pending` or `unconfirmed`, never a cookie, CSRF token or user identifier.
Storage events make other tabs hide their state. Public and protected routes,
including sign-in, remain blocked while the marker exists.

On an ambiguous failure the client calls `/api/v1/auth/me` privately. A `401`
confirms absence and clears the marker. A successful response refreshes only
the private CSRF retry value; protected content stays hidden. Retry then posts
logout with that value. Network failure keeps the unconfirmed page visible.

## Operator Diagnosis

1. Confirm whether logout returned `204`, `401`, `403` or `5xx` without logging
   cookies or CSRF values.
2. Correlate the request ID with audit-sink availability. A `5xx` after
   revocation may intentionally have no logout audit event.
3. Ask the user to keep the unconfirmed page open and retry after service
   recovery. Password change is the supported all-sessions recovery action.
4. Do not clear the browser marker manually unless server-side session absence
   has been independently established.

## Hosted Adapter Requirement

The current session compare-and-swap is process-local. A multi-process hosted
adapter must perform source check and replacement in one durable transaction,
preserve credential-version validation, reject replacement collisions and roll
back to the original record on persistence failure. Rollback to older code is
compatible because version fields default to 0, but sessions issued after a
version increment must not be accepted by a rollback that ignores the field.
Drain sessions or require reauthentication before such a rollback.
