# Deterministic assignment recommendations threat model

## Scope and assets

This model covers demand estimates, candidate rankings, team demand holds,
manager decisions and the atomic hand-off into authoritative ticket ownership,
work packages and capacity reservations.

Protected assets are personnel identity and status, team membership, competency
evidence, calendar-derived capacity, manager authority, ticket integrity, audit
evidence and the confidentiality of reasons why another person was excluded.

## Trust boundaries

- The browser supplies estimates and choices but is never an authority source.
- The API authenticates the actor and exposes only manager-authorised operations.
- PostgreSQL contains the authoritative organisation, account, competency,
  capacity, ticket and recommendation records.
- The outbox crosses into asynchronous processing and therefore carries only the
  minimum safe assignment facts.

## Threats and controls

| Threat | Control |
| --- | --- |
| Client nominates an ineligible analyst | Selection must reference an eligible candidate persisted in the preview, then every hard filter is revalidated under lock. |
| Manager grant is revoked after preview | Acceptance resolves current `task:assign` grant lineage in the transaction and fails closed. |
| Account, membership, competency or calendar changes after preview | Acceptance rechecks active account, sole home posting, team coverage, verified competency, WIP and deadline capacity. |
| Capacity is double-booked by concurrent requests | Canonical personal capacity rows are locked; one transaction creates the reservation and consumes the recommendation. |
| Two requests accept one recommendation | Recommendation and hold rows are locked, the decision is unique, and only a prepared recommendation can transition to accepted. |
| A soft override bypasses policy | Alternatives are restricted to the persisted eligible set and require an audited reason. Hard failures are never overrideable. |
| Exclusion details reveal sensitive workforce data | Public codes collapse to three safe categories. Detailed evidence hashes and relational evidence stay server-side. |
| Candidate names bypass roster visibility | Labels are enriched separately through the manager-authorised roster. Eligibility is independent of labels. |
| Client alters the ticket between preview and acceptance | The ticket version and preview hash are bound to the recommendation and checked before any write. |
| Expired holds distort team capacity | Holds have an expiry and only live prepared holds reduce aggregate availability. Acceptance rejects an expired preview. |
| Audit reason is altered | The immutable decision stores the reason and its cryptographic hash. |
| Outbox data leaks workforce evidence | The event contains recommendation, reservation and decision identifiers, not calendars or exclusion evidence. |

## Security invariants

- Named assignment is a human manager action. JIOC roles receive no new grant.
- The browser cannot override account, posting, capability, competency, WIP or
  capacity requirements.
- Personal capacity has one canonical reservation ledger. Team demand holds are
  aggregate planning pressure and never masquerade as personal reservations.
- Ticket, ownership, package, reservation, decision and hold state either commit
  together or do not change.
- Unknown or malformed workforce evidence excludes the candidate.

## Residual risks

Managers may provide inaccurate effort or capability declarations, and a valid
but poor soft-override reason can still represent a weak operational decision.
Audit review, constrained inputs and future controlled capability selection reduce
that risk but cannot eliminate human judgement. A short-lived team hold is an
estimate rather than a guaranteed future schedule, so managers must refresh stale
advice before acting.
