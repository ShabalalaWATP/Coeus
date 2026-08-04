# ADR 0050: Release-Gated Relational Authority Cutover

## Status

Accepted for implementation. No release candidate is approved by this ADR and
active authority remains disabled by default.

## Context

Sprint 24 introduces relational organisation authority, canonical calendars
and transactional task/capacity data. Local readiness checks alone cannot make
those stores authoritative. A release must bind the exact database and code
candidate to independently reviewable evidence, survive interruption between
bounded cutover steps and fail closed when deployed state differs from what was
approved.

A route-wide switch would create an unnecessarily large failure domain. A
rollback to broad legacy manager authority would also undo a security boundary.

## Decision

Istari records one immutable release candidate manifest containing:

- the application release and exact Alembic schema head;
- organisation, calendar and task/capacity source-target visibility hashes;
- the approved relational routing evaluation release;
- protected-check evidence and an independent security-review record; and
- a digest over the complete canonical manifest.

Evidence is append-only and exact-candidate bound. Approvals are separately
recorded by distinct authenticated people. A candidate creator cannot approve
their own candidate, one person cannot fulfil multiple required approval roles,
and all approval actions require fresh password reauthentication. External
checks and reviews are never inferred or fabricated by application code.

Cutover uses three ordered, independently previewed slices:

1. organisation authority;
2. canonical calendars; and
3. task ownership and capacity.

Each slice obtains its own writer fence and quiescence checkpoint, reruns its
bounded migration to convergence, records source-target visibility parity and
commits an idempotent checkpoint. An interrupted worker resumes from the last
committed checkpoint. A slice cannot start until the previous slice is
complete and the exact approved manifest still matches runtime state.

After a slice completes, the relational store is its only writer. Legacy data
is retained solely as a derived read-only projection. Recovery is forward-only:
freeze incompatible mutations, repair or restore the protected relational
backup, then resume from the recorded checkpoint. Recovery never restores
legacy route-wide authority.

Runtime composition accepts `active` only when the complete approved manifest,
all slice checkpoints and current schema/release/hash inputs match exactly.
Missing, stale, ambiguous or unavailable evidence denies startup or active
composition. `active` is never the default.

## Consequences

- Cutover is slower and deliberately operational, but each failure domain is
  small, resumable and reviewable.
- A code, schema or corpus change invalidates the candidate rather than silently
  inheriting an older approval.
- Rollback after the authority slice is a forward recovery operation, not a
  return to the previous policy.
- Operators need a coordinated backup and protected CI/security evidence before
  an approval can be valid.

## Evidence

The implementation and operating procedure are specified in the
[Sprint 24 contract](../specs/hierarchical-teams-workforce-calendars-and-task-boards.md)
and [active cutover runbook](../runbooks/sprint24-relational-authority-cutover.md).
Threats and controls are recorded in the
[Sprint 24 threat model](../threat-model/hierarchical-teams-workforce-calendars-and-task-boards.md).
