# ADR 0049: Hierarchical Organisations and Canonical Workforce Capacity

## Status

Accepted on 3 August 2026 for phased implementation. Acceptance does not
activate new runtime behaviour; each phase still requires its stated evidence.

## Context

Istari currently stores flat organisational teams containing manager/member
tuples, a single workflow kind and an optional capability-catalogue soft link.
Legacy records can place users in several teams, but teams cannot contain
descendants and management authority is either direct-team or route-area wide.
Simultaneous personnel postings are not part of the target model.

Calendar entries are stored separately for each team. This makes one person's
availability contradictory across teams and prevents a profile calendar from
being the canonical source. Availability counts all rostered people rather
than active assignment-eligible analysts and reduces live work to a binary busy
flag. JIOC routing consumes this as a binary capability availability gate.

Manager and analyst task surfaces are queues, not operational boards. Tickets
do not have leaf-team ownership before named analysts are assigned, and work
packages have no individual owner, effort, due date, dependency or blocked
state.

The requested organisational labels also include neutral commands, branches
and customer units that cannot correctly be represented by the current
`rfa|cm|jioc|qc` team-kind enum.

## Decision

If the feature contract is approved, Istari will adopt these boundaries.

1. **Separate organisational structure from delivery function.** A
   variable-depth, single-parent organisation-unit tree, initially limited to
   12 levels, represents reporting structure. Optional delivery profiles give
   selected units RFA, CM, JIOC or QC task functions. Capability coverage is
   versioned and many-to-many. Sprint 24 remains explicitly single-tenant.

2. **Use one effective home membership and action-specific management grants.**
   A user may have historic, current and scheduled membership records, but a
   database exclusion constraint permits only one effective home unit at an
   instant. Transfers use adjacent non-overlapping half-open intervals. An
   assignment-eligible analyst's home unit is exactly one RFA or CM leaf.
   Personnel transfer requires explicit authority over both source and target
   and an approved disposition for unresolved work and future commitments.
   Every descendant action, including aggregate viewing, is an explicit
   persisted grant, not an implication of another membership, role, team kind
   or parent name. Delegation retains source lineage and cascading revocation.

3. **Keep information-access policy orthogonal.** Organisation scope never
   grants ACG membership, clearance, ticket audience, draft, product or asset
   access. Every task/card/detail projection applies both organisational and
   information-object policy.

4. **Make personal schedule events canonical.** Person-owned events and
   individual capacity reservations are projected into the current home-team
   and authorised ancestor calendars. Team calendars do not store copies of
   personal events. Availability effect is separated from private detail.

5. **Keep the ticket state machine authoritative.** Team and personal Kanban
   boards are rebuildable projections over ticket state, workflow leg, team
   ownership, analyst assignments and enhanced work packages. Board actions
   invoke existing authorised workflow commands.

6. **Use deterministic eligibility, forecast and reservation.** Assignment
   candidates pass active-account, role, effective membership, capability,
   access, competency, availability, WIP and separation-of-duties filters.
   Package owners and contributors must belong to the owning leaf team.
   Pre-routing forecasts consume a versioned demand estimate. Ranking is
   versioned, persisted and explainable. Assignment reserves capacity
   idempotently and transactionally, and revalidates authority at commit.

7. **Keep receiving-team and named-person assignment human-controlled in Sprint 24.** The existing evaluated JIOC policy may auto-apply RFA versus CM using a
   minimised eligible-team feasibility gate. Deterministic team ranking remains
   advisory; a human accepts the team and named people. Models may explain
   trade-offs or propose work packages, but cannot alter hierarchy, membership,
   calendar, capacity, assignment or workflow state.

8. **Move the bounded context to relational PostgreSQL persistence.** Current
   adjacency plus closure records support hierarchy integrity and authorised
   descendant queries; immutable topology revisions support historical
   evidence. Memberships, grants, calendar events and reservations require
   transactional constraints that the whole-namespace JSON store does not
   provide. Each migration slice has one relational write authority and emits
   any temporary legacy projection through an outbox. In-memory adapters remain
   for focused unit tests. Enabling Sprint 24 with file persistence fails closed;
   the supported runtime uses local PostgreSQL and requires no cloud service.

9. **Preserve history across reorganisation.** Existing team identifiers on
   analyst assignment history remain valid. Immutable topology/path and
   decision snapshots record the hierarchy, membership and capability versions
   used at the time. Team moves, splits, merges, deactivation and membership end
   dates do not rewrite prior task ownership or calendar provenance. Historical
   context is never current access authority.

10. **Separate administration from operational activation.** Runtime mode is
    explicit: `disabled` wires nothing, `shadow` reconciles a read-only
    relational projection, `management` enables administrator command APIs
    and UI without consulting hierarchy for access or workflow, and `active`
    remains unavailable until cutover evidence passes. The one-shot bootstrap
    requires the authenticated administrator's current password, CSRF token
    and deployment-only setup nonce. Neither credential is persisted or
    returned. This boundary permits safe setup and review without an accidental
    authority cutover.

When implemented, this ADR supersedes the route-area-wide manager
scope portions of ADR 0023. It does not supersede JIOC oversight, QC-owned
release, customer decisions or existing workflow separation of duties.

## Consequences

### Positive

- Parent managers can receive bounded descendant oversight without broad
  intelligence access.
- A user updates availability once; their home-team and authorised ancestor
  views remain consistent through transfers.
- Capacity becomes assignment-eligible, deduplicated and deadline-aware.
- Team boards and individual work views use the existing workflow rather than
  creating a competing task state machine.
- Recommendations are deterministic, reproducible and safe to evaluate before
  agent activation.
- Reorganisation and temporary delegation become explicit, effective-dated and
  auditable.

### Costs and trade-offs

- Normalised hierarchy, calendar, ownership and capacity records require a
  staged migration from current JSON namespaces.
- Descendant authorisation, viewer-specific redaction and cache invalidation
  materially increase policy and test complexity.
- Capacity planning requires working patterns, effort estimates and disciplined
  lifecycle reconciliation. Missing data must remain visible as unknown.
- Variable depth remains defensively bounded at 12 levels and uses one
  organisational parent. Cross-cutting management and work relationships use
  grants, capability links or projects, never extra personnel postings or a
  multi-parent authority graph.
- External calendar connection is deferred until the internal canonical model
  is proven and remains optional for local operation.

## Rejected Alternatives

### Add `parent_team_id` to the existing JSON dataclass only

Rejected as the target architecture. It would not provide transactional cycle
prevention, effective memberships, action grants, calendar consistency or
concurrency-safe reservations. It may be used only as a temporary migration
bridge.

### Infer descendant authority from parentage or global route role

Rejected because it creates cross-branch privilege escalation and can expose
rosters, calendars or task metadata beyond operational need.

### Copy one calendar event into every team

Rejected because copies drift, conflict and leak private notes. Projections of
one canonical event provide immediate consistency.

### Let the Kanban own task state

Rejected because it would bypass or duplicate the existing state machine,
manager approval, QC and audited transition commands.

### Let an LLM choose and assign named analysts

Rejected for the initial milestone. Eligibility and capacity are policy and
transaction problems, not generative judgement. Human managers retain named
assignment authority.

## Accepted Design Evidence

- approved permission and privacy matrices;
- approved lifecycle, migration disposition and security-safe rollback design;
- approved decision-authority, numeric capacity and privacy rules;
- reviewed feature contract and threat model; and
- agreed phased acceptance and operational evidence plan.

This evidence was accepted on 3 August 2026 and permits phased implementation.
It does not activate runtime behaviour.

## Implementation Record

As of 3 August 2026, the relational organisation, exact-grant authority,
single-home membership, transfer and restructure foundations are implemented
in non-operational `management` mode. Canonical personal events now project
without copies into redacted direct-team rows and privacy-suppressed root-level
descendant daily aggregates. Aggregate and detailed reads are separate actions
whose exact grant lineage is revalidated in the same PostgreSQL transaction as
the projection. Ordinary workspace discovery now separates the actor's current
home posting from managed roots that hold both organisation-view and
workspace-view authority; it does not use extra memberships or role inference.
New analyst assignments now atomically write the ticket and its canonical
workflow-leg owner after checking the current topology revision and delivery
profile. The projection boundary is composed only when organisation mode is
`management` or `active`, so disabled mode does not partially enforce a schema
that is not authoritative. Stable synthetic delivery-team identifiers are
shared by the compatibility roster and canonical manifest. A first read-only
direct-team board is available only with an exact
`task:view` lineage and returns a bounded allowlist of operational card fields.
It does not add board mutations or a second workflow state machine. Historical
ownership backfill now runs as a bounded, digest-idempotent management-mode
reconciliation. It writes only unambiguous active route/team assignments and
records blocking findings for every unsafe case without guessing from names or
roles. Migration 0029 establishes enhanced package, dependency, participant,
working-pattern, exception and reservation ledgers. Relational assignment now
projects accountable package ownership only after rechecking the analyst's one
eligible home posting in the owning leaf team. Package completion appends
immutable history and releases reservations in the ticket transaction. The
reservation store serialises by user and uses overlap-safe 15-minute forecast
arithmetic. A management-mode package-planning boundary now exposes only one
combined previewed operation: refine effort, due date and priority, then
reserve the accountable analyst's capacity in the same serialisable
transaction. It revalidates exact `task:assign` lineage and a posting covering
the full interval, and writes immutable package, command, audit and outbox
evidence atomically. Contributor add/end is now a separate reviewed,
idempotent and serialisable command. It rechecks exact `task:assign` lineage,
the package and workflow-leg owner, the contributor's active human Analyst
account and their sole eligible home posting in the owning leaf. It advances
immutable history and audit/outbox evidence atomically, and ending
participation immediately removes My Work visibility. Reviewed dependency
add/remove is now a separate serialisable command. It locks the bounded full
package graph, revalidates exact `task:assign` authority and restricts links to
active packages in the same ticket, workflow leg and owning leaf. Cycles,
self-links, duplicates, absent removals and graph overflow fail closed, while
immutable history, command, audit and outbox evidence commit atomically.
Same-leaf accountable-owner handover is now a separate management-only,
previewed command. It binds package, ownership, participant, live-reservation
and dependency evidence, then atomically swaps accountable participation,
releases every source reservation and creates only capacity-safe like-for-like
target replacements. Exact `task:assign` lineage, the target human Analyst
account and a sole eligible posting are revalidated at commit. Immutable
command, package, audit and outbox evidence is retained. Descendant boards,
relational roster cutover and cross-team handover remain gated.
The handover boundary does not create a parallel task-access authority. The
target must already have exactly one active assignment on the authoritative
ticket aggregate for the package route and owning team. Preview binds the
aggregate version and canonical hash; execute locks and decodes that row before
locking the package, matching the assignment writer's lock order. Reassignment,
revocation, team movement or ticket lifecycle change therefore fails closed.
Product clearance and ACG policy remains enforced by product access services.
Contributor reservations are preview-bound but never dispositioned as source
capacity. Command identities are serialised by command ID and by the
actor-scoped idempotency key; replay reloads current package ownership and
cannot preserve authority after a team transfer.

The signed-in analyst now has a canonical My Work read model. It is package
participant scoped and cannot be queried for another user. A repeatable-read
query requires the package, owning unit, workflow leg and ticket aggregate to
agree, maps state through a fixed oracle, and returns a bounded field allowlist
with deterministic keyset pagination. Completed work is explicit and recent.
This is a projection only and does not create a second task mutation path.

Managers with exact current `task:assign` lineage now receive an aggregate
direct-team forecast for a bounded interval. It reuses canonical capacity
evidence and reports ready, partial or unknown without exposing people, event
notes or exclusion causes. Revision 0032 adds a password-free account
projection containing only user ID, active state, roles, credential version
and a consistency hash. The PostgreSQL state store replaces that projection
in the same transaction as the authoritative encoded account snapshot, so the
repeatable-read forecast no longer combines database evidence with a separate
in-process identity read. Missing projection rows fail closed as unknown.
The result remains advisory and the atomic package-planning command remains
authoritative until the wider cutover gates pass.

A read-only cutover-readiness report is intentionally separate from the
one-way cutover decision. It uses a bounded repeatable-read snapshot and emits
only safe check codes, statuses and counts. External routing approval, browser,
CI and security evidence remain blocking. Neither the endpoint nor its admin
panel can approve or activate a mode.

Legacy calendar migration is likewise separate from authority cutover.
Revision 0035 introduces a previewed, actor-bound and idempotent import from a
complete legacy snapshot. Stable identities preserve provenance, invalid or
colliding rows become blocking findings, and sensitive notes remain outside
history, audit and outbox payloads. Import does not delete, overwrite,
dual-write or switch any read authority.

All-day absence is interpreted at local midnight in the canonical event's IANA
time zone before capacity intersection. This removes a false unknown result for
ordinary leave without flattening civil dates into UTC. Validated daily and
weekly recurrence is expanded within a 366-day bound while preserving local
wall time across DST. The same deterministic expander now supplies personal,
direct-team, descendant aggregate, forecast and reservation reads. Occurrence
responses carry stable series and occurrence identities. Revision
`20260804_0038` retains the series as the versioned aggregate while storing a
bounded change or cancellation against one stable occurrence key. Editing this
and future occurrences truncates the original series and creates a separately
locked child series in the same serialisable transaction. The child inherits
source, owner and scope identity but receives a new event ID; obsolete future
exceptions are discarded rather than silently applied to the replacement
series. Valid exceptions feed every calendar and capacity reader. Corrupt
rules, malformed exception payloads and more than 500 candidate rows fail
closed.

Reservation identity includes the acting manager. Both first execution and
exact idempotent replay validate current `task:assign` lineage for the package's
owning leaf while holding the transaction. A different actor cannot use a known
idempotency key to retrieve or replay another manager's reservation. Capacity
reservation keys are unique by actor and key, with advisory locks on that
composite identity and the globally unique reservation ID. The same key may be
used independently by two authorised actors; one actor cannot reuse it for a
different reservation payload. This makes migration 0036 conditionally
irreversible: once two actors legitimately reuse a key, the former global
unique constraint cannot represent the evidence. Downgrade performs a preflight
and aborts atomically. Operators must remain forward or restore a coherent
pre-0036 backup; keys and immutable evidence must never be rewritten or deleted
to force rollback.

The exercise hierarchy and 53-person workforce can now be reconciled through
one fixture-specific bulk command. This is not a second organisation writer:
it is enabled only in local/test environments, targets exact stable synthetic
identifiers in the canonical PostgreSQL tables and exists because normal
single-record membership commands cannot atomically express the manifest's
future, ended and suspended lifecycle cases. Preview hashes the current
relevant rows and resolved user identities. Apply requires fresh administrator
authentication, rechecks current administrator authority, takes a global
fixture advisory lock and reruns the preview inside a serialisable transaction.
Any drift or overlap aborts the command. The adapter inserts missing records
only, writes an idempotency journal and emits one bounded audit/outbox event.
It never repairs by overwriting or deleting operator data.

Fixture capability is canonical evidence, not a profile-derived hint. Delivery
leaves receive controlled coverage rows and analysts receive verified
`assignment_competencies`; the synthetic manifest checks that each competency
belongs to the person's sole home team. Its calendar scenarios use the normal
canonical event, scope, immutable version and command ledgers. This preserves
the same read and privacy model used by manually created events while keeping
the bulk ceremony atomic.

All 40 stable routing catalogue team IDs now have explicit fixture coverage on
one of the seven delivery leaves. The internal JIOC principal has one stable,
revocable `recommendation:view` grant over the synthetic Joint User subtree.
It receives no task, roster, calendar-detail or mutation action. A new
relational context joins those mappings to the minimal account projection,
single-home eligible memberships and canonical capacity evidence in one
repeatable-read transaction. It emits only candidate identifier, status and
aggregate assignable minutes. Missing mapping, authority or mandatory evidence
is unknown. Composition can select this adapter only for the combined
`management` plus JIOC `shadow` modes, so the currently active evaluated route
path cannot consume it. The 48-case gate also requires exact paired replay,
covers all seven relational delivery leaves and permits capacity evidence only
when conserved minutes meet the approved upper demand bound. Missing, malformed,
below-range or inside-range evidence fails closed. Independent approval remains
a separate activation prerequisite.

The same manifest records 82 stable scoped management grants and 24 bounded
operational requests. Task aggregates, one workflow-leg ownership per request
and 48 two-stage packages are inserted together. Package dependencies,
accountable participants, immutable histories and idempotent create commands
are therefore canonical evidence, not UI-only examples. Existing fixture IDs,
references or incomplete supporting evidence fail the preview. A later
administrator may inspect a settled fixture without inheriting new runtime
authority or producing false drift from the original bootstrap actor.

## Required Implementation Evidence Before Activation

- hierarchy migration and phase-specific rollback proof;
- property tests for acyclicity, closure and capacity conservation;
- cross-team and descendant IDOR tests;
- calendar redaction and canonical-projection tests;
- competing-assignment transaction tests;
- RFA, raw CM and analysed CM-to-RFA end-to-end journeys;
- evaluated JIOC context release with safe stale/missing-data fallback; and
- updated user stories, diagrams, runbooks and implementation plan.

## Related Documents

- [Implementation plan and feature contract](../specs/hierarchical-teams-workforce-calendars-and-task-boards.md)
- [Planned threat model](../threat-model/hierarchical-teams-workforce-calendars-and-task-boards.md)
- [Current teams, profiles and calendars contract](../specs/teams-profiles-calendars.md)
- [Current team/calendar threat model](../threat-model/teams-profiles-calendars.md)
- [JIOC operating model](../architecture/JIOC_OPERATING_MODEL.md)
- [Workflow state reference](../architecture/WORKFLOW_STATE_REFERENCE.md)
