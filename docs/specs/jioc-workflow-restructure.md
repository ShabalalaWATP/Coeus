# JIOC Workflow Restructure

## Status

Implemented (2026-07-11). See ADR 0022. Supersedes the routing and release
behaviour described in `docs/specs/sprint-08-rfa-cm-routing.md` and
`docs/specs/manager-final-release.md`.

## Problem

Route decisions and final release both sat with the RFA and CM managers. The
organisation wants a Joint Intelligence Operations Centre (JIOC) to own the
collection-or-assessment decision, the customer to choose what happens to a
collect, managers to review their analysts' work, and Quality Control to own
the final release. Tickets also needed to support more than one analyst.

## Roles

| Role | Queue | Key additions |
| --- | --- | --- |
| Customer | Requests | No-match consent, collect choice, receipt confirmation |
| JIOC Team Member | `/jioc/queue` | `jioc:review`: route decisions with agent advice |
| RFA / CM Manager | `/rfa/queue`, `/collection/queue` | `product:approve`, `team:manage`; release permissions removed |
| Analyst | Workbench | Shared tasks (1 to 5 analysts per assignment) |
| Quality Control Manager | `/qc/queue` | QC approval performs the final release |

## State machine

```
RFI_NO_MATCH | RFI_MATCH_OFFERED -> JIOC_REVIEW
JIOC_REVIEW -> ANALYST_ASSIGNMENT (route RFA)
JIOC_REVIEW -> COLLECT_CHOICE (route CM)
JIOC_REVIEW -> INFO_REQUIRED | CANCELLED
COLLECT_CHOICE -> ANALYST_ASSIGNMENT (customer picks raw or analysed)
ANALYST_ASSIGNMENT -> ANALYST_IN_PROGRESS
ANALYST_IN_PROGRESS -> MANAGER_APPROVAL
MANAGER_APPROVAL -> ANALYST_IN_PROGRESS (rework) | QC_REVIEW
QC_REVIEW -> REWORK_REQUIRED | DISSEMINATION_READY | ANALYST_ASSIGNMENT
REWORK_REQUIRED -> QC_REVIEW (analyst resubmits straight to QC)
```

Retired states decode through `TicketState._missing_` aliases:
`ROUTE_ASSESSMENT`, `RFA_MANAGER_REVIEW` and `CM_MANAGER_REVIEW` map to
`JIOC_REVIEW`; `MANAGER_RELEASE` maps to `QC_REVIEW`. Demo tickets that were
awaiting the retired manager-release step reappear in the QC queue for a
benign re-approval; this is accepted for local demo data.

## JIOC routing

- `GET /routing/jioc/queue` lists tickets in `JIOC_REVIEW` and
  `COLLECT_CHOICE` (the latter so JIOC can see requests awaiting the
  customer), priority-sorted with cursor pagination.
- `POST /routing/{id}/run` records capability reviews and the orchestrator
  recommendation; the state stays `JIOC_REVIEW` (agents advise only).
- `POST /routing/{id}/approve` records an audited `ManagerRoutingDecision`.
  Route `rfa` moves to `ANALYST_ASSIGNMENT`; route `cm` moves to
  `COLLECT_CHOICE` and posts a display-only chatbot notice telling the
  customer to choose in the panel. Approving against the recommendation
  requires an override reason (minimum 3 characters).
- Rejection and clarification keep their existing behaviour and move the
  ticket to `INFO_REQUIRED`; resuming with new information returns it to
  `JIOC_REVIEW`.

## Collect choice

`POST /tickets/{id}/collect-choice` with `{"analysed": bool}` is owner-only,
CSRF-validated and audited. It stores `collect_disposition` ("raw" or
"analysed") and moves the ticket to `ANALYST_ASSIGNMENT` on the CM route. Raw
collects still pass QC before release.

## Team production

- `POST /analyst/tasks/{id}/assign` takes `analystUserIds` (1 to 5 distinct
  active analysts). Fresh assignment is blocked only while ACTIVE assignments
  exist for the current approved route, so the RFA follow-up leg of an
  analysed collect is not blocked by the completed CM leg. Reassignment
  deactivates the route's previous assignments instead of overwriting them.
- Every active assignee sees the shared task; `POST /analyst/tasks/{id}/submit`
  moves first submissions to `MANAGER_APPROVAL` and QC-requested rework
  straight back to `QC_REVIEW`.
- `POST /routing/{id}/manager-approval` (permission `product:approve` plus the
  route's review permission) forwards to `QC_REVIEW`;
  `POST /routing/{id}/manager-rework` returns the work with a recorded reason.
  A manager who drafted the work or holds an active assignment cannot approve
  it (`separation_of_duties`).

## QC release

QC approval validates the checklist, metadata and ACGs, ingests the draft as a
DRAFT product, then completes in one compensated step:

- Normal case: publish the product, record dissemination and a feedback
  request, move to `DISSEMINATION_READY`, audit `qc_approved` and
  `product_released`, and notify the requester (best effort, with a
  `product_release_notification_failed` audit fallback).
- Analysed collect (`approved_route == CM` and `collect_disposition ==
  "analysed"`): append an APPROVED RFA routing decision by the QC actor, link
  the collect product to the ticket for the RFA analysts, deactivate the CM
  leg's assignments and move to `ANALYST_ASSIGNMENT`. The collect stays DRAFT
  and is never released to the customer. The QC approval's ACGs must include a
  group the RFA analysts hold or the linked collect is invisible to them
  (covered by tests).

Any failure after ingestion restores the original ticket and discards the
ingested product so approval can be retried without orphans; if persistence
itself is down the restore is best-effort but the discard always runs.

## Permission refresh on restore

`SeedUserRepository` re-derives every restored user's permissions from their
persisted roles at startup, so role-definition changes (grants and
revocations) apply to existing accounts. Without this, managers kept the
removed release permissions and never gained `product:approve` on upgraded
local stores.

## Tests

Backend: `test_routing_api.py`, `test_collect_choice_api.py`,
`test_manager_approval_api.py`, `test_qc_api.py`, `test_qc_release_api.py`,
`test_cm_analysed_leg_api.py`, `test_qc_hardening_api.py`,
`test_auth_service.py` (permission refresh), plus legacy-decode cases in
`test_domain.py` and `test_persistence_codec.py`. Web: routing queue (JIOC and
team modes), manager approval panel, collect choice panel, analyst workbench
submit flow and the rewritten full-workflow e2e. Both suites hold the 95%
coverage gates and the flow was verified live end to end, including the
CM-to-RFA leg.
