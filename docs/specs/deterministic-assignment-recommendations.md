# Deterministic assignment recommendations

## Purpose

Give an authorised manager reproducible, evidence-backed advice when assigning an
RFA or CM work item to a named analyst. The recommendation is advisory. The
manager remains accountable for the named assignment, and JIOC agents cannot
accept it on the manager's behalf.

## Scope

The feature persists a versioned estimate of the work demand, ranks eligible
analysts, places a short-lived hold against the recommended team's aggregate
capacity, and lets the manager accept the first choice or a reasoned alternative.
Acceptance updates the ticket, ownership, projected package and personal capacity
reservation in one database transaction.

It does not autonomously assign people, infer capabilities from sensitive free
text, move personnel between teams, or create another personal-capacity ledger.

## Demand contract

Each preview records:

- a workflow leg, effort range, working window, deadline and manager-declared
  capability identifiers;
- the ticket version and a stable source hash;
- an incrementing estimate version for the ticket and workflow leg;
- an expiring recommendation, ranked candidates and exclusion totals; and
- one team-level demand hold for the leading candidate's home team.

A changed estimate creates a new version. Historic estimates and decisions remain
immutable audit evidence. Capability identifiers are declared input, not a claim
that an automated model has established the task's requirements.

## Eligibility and ordering

The store fails closed. A candidate must have all of the following at preview and
again at acceptance:

1. an active Analyst account;
2. exactly one assignment-eligible home posting for the complete work window;
3. a home team able to deliver the requested workflow leg and capabilities;
4. current, verified evidence for every required competency;
5. active work below the configured WIP limit;
6. enough remaining personal capacity before the deadline; and
7. enough aggregate team capacity after other live demand holds.

Hard eligibility failures cannot be overridden. Eligible candidates are ordered
deterministically by active WIP ascending, assignable minutes descending, home
team UUID ascending, then analyst UUID ascending. The persisted rank and evidence
hash make a preview reproducible.

The API only exposes safe explanation or exclusion categories:
`not_currently_eligible`, `capacity_unavailable` and `data_unknown`. It does not
reveal another person's calendar, competency evidence, account state or detailed
reason for exclusion. Display names are enriched only from the manager-authorised
roster.

## Manager journey

1. The manager opens assignment advice from the existing named-assignment panel.
2. They enter a bounded effort range, deadline and capability identifiers.
3. The application shows the eligible ranking, available minutes, current WIP,
   estimate version and recommendation expiry.
4. The first-ranked candidate is selected by default.
5. Selecting another eligible candidate requires a meaningful reason of at least
   ten characters. This is a soft override, never a hard-filter override.
6. Acceptance uses the existing assignment command and its authoritative workflow
   transaction. Success closes the preview and refreshes the ticket.
7. If evidence changed, the ticket is stale, the preview expired, or capacity was
   consumed, acceptance is rejected without a partial write. The manager prepares
   a fresh preview.

## Atomic acceptance

The relational transaction locks and revalidates the recommendation, demand hold,
ticket version, manager grant lineage, account, home posting, capability,
competency, WIP and capacity. It then writes the named ownership, advances the
first pending projected package, creates the canonical personal capacity
reservation, records the decision, consumes the team hold, and emits the bounded
assignment event. Any failure rolls back every change.

## Acceptance criteria

- Repeating a preview against unchanged evidence produces the same ordering.
- Suspended accounts, expired competency, overlapping home postings, missing team
  delivery coverage, exhausted capacity and WIP-at-limit candidates are excluded.
- Revoked manager grants, stale ticket versions and expired recommendations fail
  closed at acceptance.
- Concurrent acceptance attempts create one decision and one capacity reservation.
- A reasoned alternative can be accepted only when it was persisted as eligible.
- Raw private eligibility evidence is absent from API responses and outbox events.
- Direct named assignment remains available and subject to its existing manager
  authority checks; no JIOC permission is introduced.

## Verification

Unit tests cover deterministic hashing, request validation and safe codes. Real
PostgreSQL tests cover versioning, team holds, ranking, atomic acceptance, soft
override, changed account evidence, expiry and concurrent acceptance.
