# Threat Model: JIOC Workflow Restructure

Scope: the JIOC routing stage, collect choice, manager approval chain,
QC-owned release and the CM-to-RFA leg. Supersedes
`docs/threat-model/manager-final-release.md`.

## Assets

- Route decisions and their audit trail (who sent work to collection).
- The customer's collect disposition (raw vs analysed).
- Unreleased DRAFT products, especially collects awaiting analysis.
- Release authority: what becomes visible to the requester and when.
- Analyst assignment history.

## Trust boundaries and controls

| Threat | Control |
| --- | --- |
| A non-JIOC user decides routes | `jioc:review` gates the queue and decisions; managers no longer hold route authority |
| Route decision forged against agent advice without trace | Overrides require a recorded reason; every decision is an audited `ManagerRoutingDecision` |
| Someone other than the requester chooses the collect disposition | Collect choice is owner-only (collaborators and admins get 404/409), CSRF-validated and audited |
| JIOC oversight exposes analyst work content | The bounded JIOC-only projection returns identifiers, workflow state, team ownership and aggregate load counts, never intake text, notes, drafts or products. |
| Rejected work is resubmitted unchanged | Submission requires a draft created after the latest manager return or QC rejection. |
| A manager approves their own drafted work | `separation_of_duties`: drafting or actively assigned users cannot manager-approve; QC keeps its own drafter check |
| The wrong team's manager approves work | Approval requires the route's review permission and `product:approve`; the other route's manager gets 403/404 |
| Release without quality control | Only QC approval releases; managers lost `product:publish` and `product:disseminate` |
| A raw collect leaks to the customer during the analysed flow | The forwarded collect stays DRAFT, is never disseminated, and store search excludes it; verified by API tests and the live walk-through |
| The RFA analysts cannot see the collect they must analyse (silent filter) | QC's ACG selection must include a group the analysts hold; covered by the CM-to-RFA leg test |
| Orphaned products after a mid-release failure | QC approval compensates: the ticket is restored and the ingested product discarded on any failure after ingestion; the discard runs even if the restore itself fails |
| Notification failure blocks or fakes a release | Notification is best-effort after the committed release, with a `product_release_notification_failed` audit fallback |
| Stale persisted permissions keep revoked privileges alive | `SeedUserRepository` re-derives permissions from persisted roles on startup, so revocations (and grants) reach existing accounts |
| Legacy persisted states crash decoding or skip review | Enum `_missing_` aliases route retired states back into reviewed queues (`JIOC_REVIEW`, `QC_REVIEW`) rather than past them |

## Residual risks

- Demo tickets caught in the retired `MANAGER_RELEASE` state are re-approved
  by QC; the duplicate approval is benign but appears twice in the timeline.
- Availability counts expose aggregate team workload numbers to team members;
  no ticket content is exposed (see the teams threat model).
