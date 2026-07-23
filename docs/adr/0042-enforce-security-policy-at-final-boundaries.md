# ADR 0042: Enforce security policy at final boundaries

## Status

Accepted, 21 July 2026.

Implementation state: integrated into `main` at `0cde7010` for supported
synthetic local/test use. Release state: finding and production closure remain
open. See the [remediation contract](../specs/security-scan-remediation-2026-07-22.md)
and [threat model](../threat-model/security-scan-remediation-2026-07-22.md).

## Context

Standard security scan `59eb4efa-4acb-4504-b43c-bdab86f43cd7` found repeated
cases where a useful control existed but ran at the wrong boundary: broad domain
state reached a narrower response, authority was checked before long-running
work rather than at commit, file limits ran after parsing, and provider limits
ran after buffering or only between chunks.

Removing affected features would close paths but break supported workflows.
Adding route-specific checks alone would leave equivalent sinks able to drift.

## Decision

Keep supported workflows and enforce each invariant at the last boundary that
can safely decide it:

- External responses use explicit caller-specific projections for protected
  derived state and metadata. Global audit access remains an Administrator
  capability, distinct from bounded JIOC oversight.
- Privileged mutation paths include current actor and material relationship
  authority in their final conditional decision. Signed request tokens bind a
  request but do not preserve mutable action permission.
- Product bytes receive content-derived admission before durable publication.
  Semantic document checks and resource budgets run before or during the work
  they govern.
- Provider transports stream before decoding, apply byte ceilings while reading
  and enforce a monotonic total deadline as well as inactivity timeouts.
- Offset pagination receives an explicit maximum result window while preserving
  the current response contract; keyset pagination remains the preferred future
  design for large catalogues.

Every denial path has a positive compatibility control through the same public
or service boundary. Unsafe state fails explicitly and is never silently
truncated, accepted or published.

## Consequences

- Valid role journeys, product workflows, document types, provider calls and
  normal pagination remain supported.
- Revocation becomes meaningful for already-issued tokens and in-flight work.
- Some formerly accepted unsafe XML variants, stale operations and extreme page
  requests now receive explicit client errors.
- Repository and service interfaces may carry additional freshness evidence,
  making security dependencies visible rather than implicit.
- Parser isolation, typed file verdicts, keyset pagination and dedicated
  oversight read models remain eligible follow-on hardening when production
  scale justifies their operational cost.
- A fresh security scan and staging verification remain required before a
  production release claim.

## Follow-up implementation, 22 July 2026

Follow-up scan `5af0222d-05d1-4c46-a090-018aff45db2d` showed that this decision
was not yet applied universally. Eight protected writes lacked atomic current
actor authority at commit, and three parser paths enforced limits after
semantic expansion or failed to normalise parser failure.

The remediation applies this existing decision without introducing a new
deployment boundary. Administrator role, clearance and status changes now
atomically validate actor and target. Five workflow mutations carry an exact
live `UserAccount` expectation and required permission to a PostgreSQL users-row
lock or the local `authority_guard`; alternate compositions fail closed. QC
publishes only inside guarded confirmation. Interactive chat, active-work, RFI
and QC release commits also require the exact initiating session. RFI confirms
requester active-ACG membership, then locks and revalidates the union of offered
and persisted grounded-evidence product IDs. QC confirms team, draft,
release-ACG and recipient visibility. Active-work results and audit commit
atomically.

Workflow and submission paths acquire mutable authority in one canonical order:
users, sessions, access, teams, products, then ticket. The unified order is part
of the security contract rather than an adapter-specific optimisation.

Provider JSON is bounded to depth 32. PDF content and Form streams are bounded
per stream and document, by stream and Form invocation count, by operation count
and by Form depth. Resource inheritance, missing resources, repeated Forms and
cycles are handled explicitly. DOCX cell, depth and work limits run before
`python-docx`, and analyst document parsing uses `asyncio.to_thread`. Staging,
multipart exit and submission preserve admission and the staged file across
cancellation until parser exit. This keeps the supported local topology but does
not make third-party parsing a process sandbox. The
[detailed values and evidence](../specs/security-scan-remediation-2026-07-22.md)
passed full repository gates. Authorised staging and a fresh sealed
whole-repository deep scan of the exact immutable candidate remain open.
