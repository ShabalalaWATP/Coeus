# Sprint 24 Relational Authority Cutover

Use this runbook only for an explicitly scheduled Sprint 24 release. Routine
administration, readiness viewing and shadow validation do not require a
cutover. The application does not create protected-check, security-review or
independent approval evidence on an operator's behalf.

## Preconditions

1. Confirm PostgreSQL is healthy and Alembic is at the exact schema head named
   in the candidate.
2. Take and verify a coordinated logical backup, including security epochs,
   revocation checkpoints and every Sprint 24 cutover table. Follow the
   [coordinated backup and restore runbook](coordinated-backup-restore.md).
3. Run the full backend, frontend, real-PostgreSQL, version-skew, browser and
   security suites through protected CI.
4. Record the protected workflow identity, immutable result digest and source
   reference. A locally asserted green result is not protected-CI evidence.
5. Record the independent security review and the approved relational routing
   evaluation release.
6. Create a candidate from the current schema, release and the three bounded
   source-target parity snapshots. Preserve the returned manifest digest.
7. Have separate authorised people review and approve the exact candidate.
   The creator cannot approve it, each required role must be fulfilled by a
   different person, and every approval requires fresh reauthentication.

Do not proceed if any manifest field, evidence digest, runtime release, parity
hash or schema head changes. Create and independently review a new candidate.

## Slice procedure

Perform the following procedure in order for `organisation`, `calendar`, then
`task_capacity`. Do not combine slices.

1. Request a fresh read-only preview. Check the manifest digest, predecessor
   checkpoint, planned row counts, blockers and source-target visibility hash.
2. Announce the bounded write pause and obtain the slice writer fence. Existing
   reads may continue, but new writes in the slice must fail safely or wait
   behind the fence.
3. Wait for bounded quiescence. If the timeout expires, release the fence and
   investigate. Never bypass quiescence.
4. Execute using the exact preview identifier. Execution rechecks the current
   schema, release, approvals, evidence, predecessor, fence and visibility
   inputs inside the transaction.
5. Rerun the idempotent migration to convergence. Compare current-authority
   source visibility with target visibility for every permitted principal.
6. Commit the parity result, new relational write-authority state, read-only
   legacy-projection state and immutable checkpoint together.
7. Release the fence and monitor denied writes, parity alarms, queue lag and
   audit/outbox delivery before previewing the next slice.

## Interruption and resume

Execution is checkpointed and actor-scoped. After a process or host failure:

1. keep writes for the affected slice fenced;
2. inspect the immutable attempt and last committed checkpoint;
3. verify the candidate, database head, writer-fence generation and parity
   inputs still match;
4. resume the same attempt rather than starting an overlapping command; and
5. release the fence only after the checkpoint and visibility parity commit.

A second worker must not execute the same or a later slice concurrently.
Stale previews, a changed fence generation or version-skewed clients are
rejected.

## Forward-only recovery

After organisation authority is cut over, never set legacy policy or route-wide
manager authority back to writable/authoritative.

- Freeze incompatible mutations and keep current relational authorisation.
- Apply a reviewed forward repair when integrity evidence identifies a bounded
  discrepancy.
- If repair is unsafe, restore the verified relational backup, replay monotonic
  revocation/security checkpoints, invalidate sessions and resume the same
  slice from its durable checkpoint.
- Keep the legacy projection read-only throughout recovery.
- Re-run visibility parity and create a new exact candidate if code, schema or
  evidence changed.

## Activation verification

Set active runtime configuration only through the separately controlled
deployment process after all three checkpoints are complete. Startup must
refuse active composition unless the complete approved manifest matches the
current schema head, application/routing release and parity hashes. Confirm
that organisation, calendars and task/capacity reads use relational authority,
legacy projections reject writes and established workflow journeys remain
green.
