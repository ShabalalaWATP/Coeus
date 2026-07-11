# ADR 0022: JIOC Routing, Manager Approval Chain and QC-Owned Release

## Status

Accepted (2026-07-11).

## Context

The original workflow gave the RFA and CM managers two unrelated jobs: deciding
whether a request needed collection or assessment, and releasing the finished
product after Quality Control. Neither decision sat with the people best placed
to make it. Route decisions belong to a joint routing cell that sees both
queues; release belongs with the quality gate that just checked the product.
The workflow also supported only a single analyst per ticket and had no formal
manager review of analyst work before QC.

## Decision

1. **JIOC decides routes.** A new JIOC Team Member role owns a single routing
   queue (`JIOC_REVIEW`). The capability and orchestrator agents advise; the
   JIOC member decides whether collection is required (route CM) or not (route
   RFA). The retired states `ROUTE_ASSESSMENT`, `RFA_MANAGER_REVIEW` and
   `CM_MANAGER_REVIEW` decode to `JIOC_REVIEW` via a legacy alias so persisted
   tickets still load.
2. **The customer chooses the collect disposition.** When JIOC routes to CM the
   ticket pauses in `COLLECT_CHOICE` until the requester picks "raw collect
   only" or "collect plus RFA analysis". The choice is owner-only, recorded on
   the ticket (`collect_disposition`) and audited.
3. **Managers lead teams instead of releasing.** Team managers assign one to
   five analysts, and analyst submissions now stop at `MANAGER_APPROVAL` where
   the owning manager either forwards to QC or returns the work with a reason.
   Separation of duties: a manager who drafted or is assigned to the work
   cannot approve it.
4. **QC owns the final release.** QC approval publishes the product, records
   dissemination and feedback requests, and notifies the requester in one
   audited, compensated step (`services/qc_release.py`). The retired
   `MANAGER_RELEASE` state aliases to `QC_REVIEW`; demo tickets caught mid
   release reappear in the QC queue for a benign re-approval. For an analysed
   collect, QC approval instead forwards the ticket to RFA assignment with the
   collect product linked and still DRAFT; only the RFA leg's QC approval
   releases to the customer.
5. **Permissions derive from roles at restore.** Persisted user records used to
   keep the permission snapshot from seed time, so code-level revocations (for
   example removing `product:disseminate` from managers) never reached existing
   accounts. `SeedUserRepository` now re-derives permissions from the persisted
   roles on every startup.
6. **Teams, profiles and calendars are first-class.** Organisational teams
   (people and access) are separate from the advisory capability catalogue and
   carry a soft `capability_team_id` link. Members self-report availability on a
   team calendar; managers write for their own team; a deterministic
   availability service combines the calendar with live analyst assignments so
   assignment decisions can see who is free.

## Consequences

- Route and release authority are now single-purpose and auditable; managers
  keep team leadership plus store uploads (`product:create_existing`) but lose
  publish/disseminate.
- Multi-analyst assignment keeps history: reassignment and the CM-to-RFA
  handover deactivate earlier assignments rather than overwriting them.
- The RFI-to-delivery path gains two customer decisions (no-match consent and
  collect choice) and one manager decision (approval) without any autonomous
  agent action.
- Legacy state and role strings persist in old records; enum `_missing_`
  aliases keep them decodable indefinitely.
