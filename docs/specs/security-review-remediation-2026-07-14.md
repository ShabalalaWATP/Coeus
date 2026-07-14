# Security Review Remediation, 2026-07-14

## Goal

Close the eight validated findings from sealed standard security review
`87a10d13-14af-48cc-a361-72470abc8d8d` of revision
`752d32ae7cc4d968961135a6336b60f494a76e17`, including bypass variants
identified while implementing the fixes. This review is the current
application baseline. It does not replace Sprint 17's outstanding
clean-candidate deep-scan gate.

## Security Invariants

- Creating an existing Store product defaults to `draft`. Explicit
  `published` creation requires `product:publish` on both JSON and multipart
  paths. Unsupported initial lifecycle states are rejected before persistence.
- Session rotation is an atomic replacement and cannot revive a session removed
  by logout or password change. Credential versions invalidate sessions and
  stale old-password logins after any credential change.
- Ticket collaboration edit authority does not imply lifecycle authority. Only
  the requester or an actor with `ticket:transition` may submit a ticket.
- Login, registration and administrative password work share one bounded
  Argon2 admission pool. Saturation fails fast with a generic `429`.
- A failed browser logout never presents anonymous sign-in as if server
  revocation succeeded. Protected data is hidden immediately, pending state is
  persistent and cross-tab, and a refreshed CSRF token can be used for retry.
- External analyst product links accept only currently visible, published
  Store products. Ticket-local analyst drafts remain in the dedicated draft
  workflow and cannot be converted into another participant's Store audience.

## Acceptance Criteria

- Deterministic tests reproduce both orderings of logout, rotation and password
  change races, concurrent rotations, persistence rollback and stale-password
  login.
- Route tests prove shared Argon2 admission across login and registration and
  prove denied registration reservations are released.
- Publication tests cover denied and authorised JSON creation, omitted status,
  invalid states and multipart bypass attempts without product or byte residue.
- Ticket tests cover owner, editor, write-all-only and transition-only actors,
  with no mutation or audit side effect on denial.
- Analyst tests deny invisible drafts and creator-visible drafts while retaining
  a positive published-product control.
- Frontend tests cover non-publisher controls, delegated ticket submission,
  protected-state hiding, stale-CSRF retry, logout deduplication, reload-safe
  unconfirmed state, focus and status announcements.
- Backend and frontend line and branch coverage remain at least 95 percent, and
  formatting, lint, type, architecture, contract and file-line gates pass.
- The security fix report maps every original finding to code and verification
  evidence. A fresh deep scan is still required for Sprint 17 release closure.
