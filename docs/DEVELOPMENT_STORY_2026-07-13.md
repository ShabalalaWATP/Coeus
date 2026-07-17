# Coeus Development Story: 2026-07-13

## Security repair and hardening

- Added atomic assigned-QC self-claim. Safe summaries precede assignment; one
  eligible reviewer owns detail, decisions and linked-draft audience. Audited
  release, rework retention, separation of duties, one-winner memory/PostgreSQL
  tests and local/relational Store-search parity close the audience gap. The
  final candidate passes 962 backend tests at 98.15 percent line and 95.08
  percent branch coverage, 414 frontend tests at 98.69 percent line and 95.00
  percent branch coverage, and all ten disposable-PostgreSQL browser stages.
- Introduced the application-owned workflow transaction port and cut hosted
  PostgreSQL QC release over to one version-checked ticket, Store, audit and
  notification transaction. Audit failure rolls the unit back; concurrent
  adapters produce one commit and one conflict.
- Cut requester cancellation, no-match consent, collect choice and delivery
  confirmation over to the same hosted ticket-and-audit transaction while
  retaining API responses and atomic single-process compatibility behaviour.
- Extracted `TicketMutationService` for collision-safe creation, single-ticket
  updates, deterministic paired links and batched join audits, removing hosted
  save-then-audit compensation while preserving existing audit events.
- Added hosted outbox delivery with strict payload validation, requester
  resolution, fenced retries and durable in-app/email event-ID deduplication.
  Conflicting content for the same aggregate version fails closed.
- Verified Ruff, strict mypy, architecture and line gates. The full 838-test
  memory, file and PostgreSQL suite passed at 97.29 percent combined line and
  branch coverage.
- Cut persistence writers over to semantic stable type and enum IDs after
  validating dual-format readers and identity goldens. Migration `0012` now
  converts legacy ticket rows and reconciles canonical hashes before relational
  mutation; relational startup rejects hash, identity and projection drift.
- Expanded CI boundaries and config/docs drift gates. Frontend format, lint,
  type, Knip, tests, production audit and build pass at 98.63 percent lines,
  95.10 percent branches and 96.21 percent functions.
- Projected ticket requester, lifecycle state and capacity into indexed
  relational columns. Store reads use draft audiences with revocation tests;
  full reconciliation remains open.
- Added dry-run-first, advisory-locked ticket-capacity recovery with scoped
  cleanup, validated projection repair and drained-only release. Mutations are
  audited and focused tests pass.
- Added a quiesced N-1 compatibility bridge. It verifies relational hashes,
  emits legacy IDs, rejects drift or malformed state and normalises N-1 writes
  back to stable IDs. A detached immutable N-1 worktree proved old and current
  writes against a disposable PostgreSQL database.
- Removed the local scanner findings: Bandit, pip-audit, Semgrep, Gitleaks,
  Checkov and high/critical Trivy image checks are clean on the candidate.
- Added a digest-pinned PostgreSQL browser gate. Ten real Chromium stages now
  prove explicit draft registration, same-ACG search, known-detail and asset
  grant denial, `413` recovery without mutation, `429` recovery without lost
  input, customer intake, JIOC routing, RFA assignment, analyst production,
  manager approval, QC release, Store search and exact downloaded asset bytes.
  Published remains the upload default, preserving existing registration.
- Added the provisional per-finding closure ledger. Formal closure still needs
  the remaining audience/recovery browser matrix and authorised staging
  topology. PR 109 protected checks passed on substantive candidate
  `a02fd6d3`. The repository owner explicitly deferred the fresh sealed scan on
  2026-07-13, so fresh-scan closure is not claimed.
