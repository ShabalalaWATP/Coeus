# Security Review Remediation Evidence, 2026-07-14

## Scope And Baseline

This ledger records the remediation candidate for sealed standard security
review `87a10d13-14af-48cc-a361-72470abc8d8d` of immutable revision
`752d32ae7cc4d968961135a6336b60f494a76e17`. The review validated eight
findings. It is the current application finding baseline. This file does not
erase the historical 2026-07-13 Sprint 17 ledger and does not claim the
outstanding clean-candidate deep scan has run.

All examples and tests use synthetic `example.test` identities and mock data.

## Finding Traceability

| Finding | Remediation | Regression evidence |
|---|---|---|
| Unauthorised direct product publication | Product creation defaults to draft. The shared ingestion policy requires `product:publish` for explicit publication and rejects unsupported initial states. | `test_store_publication_authorisation.py`, including JSON and multipart denial, default draft and authorised publication. |
| Password-change/session-rotation race | Rotation uses repository compare-and-swap. Sessions capture a monotonic credential version advanced by password changes and administrative resets. | `test_session_rotation_races.py`, including both race orderings, concurrent rotations, persistence rollback and stale old-password login. |
| Logout/session-rotation race | Logout requires deletion of the current session; a losing logout returns authentication failure and cannot claim success. Revocation is not rolled back on audit failure. | `test_session_rotation_races.py`, `test_auth_rollback.py`. |
| Collaborator editor submits owner ticket | Submission reads only a visible ticket, then requires requester ownership or `ticket:transition`. `ticket:write_all` and editor access are insufficient. | `test_ticket_collaborators_api.py`, `test_ticket_submission_authorisation.py`, `RequestsPage.viewer.test.tsx`. |
| Registration Argon2 exhaustion | Registration hash work uses the shared bounded password-work pool and releases its pending reservation on rejection. | `test_password_capacity_routes.py`, `test_passwords.py`. |
| Failed browser logout appears complete | Protected session and query data are hidden before the request settles. Pending state persists and broadcasts across tabs, blocks public routes, deduplicates requests and refreshes CSRF privately for retry. | `auth-context.test.tsx`, `auth-context.logout.test.tsx`, `LogoutUnconfirmedPage.test.tsx`. |
| Login Argon2 exhaustion | Known and unknown login verification uses the same bounded pool and returns the same generic capacity error. | `test_password_capacity_routes.py`, `test_passwords.py`. |
| Draft audience link creates its own authority | External analyst links require a currently visible published product. Creator-visible and unrelated drafts cannot be linked into a task or create projection authority. | `test_analyst_draft_link_security.py`, `test_analyst_linked_product_reauthorisation.py`, `test_analyst_api.py`. |

## Bypass Review Additions

- Credential-version checks close the sibling old-password login interleaving,
  not only the original rotation path.
- Publication authority is enforced in the service used by JSON and multipart
  routes.
- Ticket lifecycle authority is independent from both collaborator editing and
  global write authority. The frontend reflects the same permission matrix.
- Draft linking is published-only because actor-level draft visibility cannot
  prove that the draft belongs to the target ticket.
- Logout retry survives reload, stale CSRF and concurrent calls without
  restoring protected content.

## Verification State

The final local candidate passes:

- Backend: 68 PostgreSQL tests and 915 non-PostgreSQL tests, with 98.13 percent
  line coverage and 95.01 percent branch coverage.
- Frontend: 432 tests, with 98.51 percent line coverage and 95.01 percent branch
  coverage. The auth/password slice passes 28 focused regressions, including
  stale initial-load, login, refresh and password-rotation completions, plus
  reordered current-session verification during logout.
- Ruff lint and format, mypy, ESLint, TypeScript, Prettier, production build,
  dead-code, architecture, contract, documentation, N-1 compatibility,
  security-policy and 350-line gates.
- Bandit, `pip-audit --skip-editable` and the production frontend package audit;
  both dependency audits report no known vulnerabilities.

This closes the eight standard-review findings in the local remediation
candidate. Sprint 17 release closure still requires an immutable clean
candidate, authorised staging evidence and a fresh sealed deep scan under
`docs/security/SECURITY_REPAIR_AND_HARDENING_PLAN.md`.
