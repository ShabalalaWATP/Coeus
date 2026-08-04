# Organisation and Workforce Data Dictionary

Status: **management and shadow implementation**. The relational records below
are authoritative inside their bounded management commands. They do not become
the live application-wide authority until the separately approved cutover.

This dictionary explains Sprint 24 organisation, workforce, calendar, task and
capacity data. It complements [ADR 0049](../adr/0049-hierarchical-organisations-and-canonical-workforce-capacity.md),
the [feature contract](../specs/hierarchical-teams-workforce-calendars-and-task-boards.md)
and the [threat model](../threat-model/hierarchical-teams-workforce-calendars-and-task-boards.md).

## Authority model

Istari separates five kinds of authority:

| Boundary | Authoritative source | What it controls |
| --- | --- | --- |
| Identity | Account snapshot plus minimal relational account projection | Active state, roles and credential revocation |
| Organisation | Units, topology revisions, memberships and scoped grants | Home team, management scope and permitted actions |
| Workflow | Encoded `TicketRecord` aggregate | Request state, audience and assigned analysts |
| Team work | Workflow-leg ownership and canonical work packages | Owning delivery leaf, accountable work and dependencies |
| Capacity | Working patterns, calendars, exceptions, demand holds and reservations | Conserved time available for assignment |

No organisation relationship grants ACG membership, clearance, ticket audience,
product access or asset access. Those policies remain independent and are
rechecked when an object is opened.

## Organisation records

| Record | Purpose | Important invariants |
| --- | --- | --- |
| `organisation_units` | Effective-dated hierarchy nodes | Stable UUID, bounded text, one parent, active interval and version |
| `organisation_unit_closure` | Current ancestor/descendant paths | One self row at depth zero, maximum depth 12, no cycle |
| `organisation_topology_revisions` | Immutable parent/path history | Path ends at the unit, contains unique nodes and matches the parent |
| `team_delivery_profiles` | Declares a delivery leaf and route | Leaf-only delivery authority, route, WIP limit and version |
| `team_capability_coverage` | Versioned team capability evidence | Controlled capability identifier, proficiency and validity |
| `team_memberships` | Effective-dated personnel posting | At most one non-overlapping effective home posting per person |
| `team_management_grants` | Direct or descendant action grant | One action, bounded lineage, validity interval and revocation state |
| `effective_authority_epochs` | Cache/final-boundary invalidation version | Advances when relevant authority changes |
| `organisation_reconciliation_checkpoints` | Legacy projection checkpoint | Source digest, bounded run status and immutable outcome |
| `organisation_reconciliation_findings` | Safe drift evidence | Allowlisted code, severity, object identity and resolution state |

Membership is a posting, not a second login or group shortcut. A transfer ends
the source interval exactly when the target interval begins. Simultaneous
postings are rejected regardless of route or capacity.

## Organisation commands and evidence

Lifecycle commands use preview, reviewed execution and actor-scoped idempotency.
Dedicated command/history records cover bootstrap, unit mutation, reparenting,
membership, personnel transfer, deactivation, merge, split and grants. Each
successful mutation commits its domain rows, immutable history, audit event and
outbox event together. A stale preview, changed lineage or reused identity with
a different payload fails without a partial mutation.

## Action dictionary

| Action | Meaning |
| --- | --- |
| `organisation:view` | View named unit metadata in the granted scope |
| `organisation:view_aggregate` | View privacy-safe descendant aggregates |
| `roster:view` | View the direct authorised roster |
| `roster:manage` | Add, suspend or end postings within scope |
| `roster:transfer` | Transfer a person between two explicitly authorised units |
| `calendar:view_availability` | View redacted availability rows or aggregates |
| `calendar:view_detail` | View allowlisted detailed calendar fields |
| `calendar:manage` | Create or change manager-owned commitments |
| `task:view` | View workflow-derived team work |
| `task:assign` | Plan packages and reserve accountable capacity |
| `task:approve` | Perform the existing authorised approval command |
| `task:transfer` | Propose or accept a controlled work transfer |
| `recommendation:view` | View bounded deterministic recommendation evidence |
| `recommendation:override` | Override a soft ranking factor with a reason |
| `workspace:view` | Open an integrated team workspace |
| `workspace:configure` | Change bounded team workspace settings |
| `workspace:export` | Request an expiring, audited workspace export |
| `work_update:view` | Read scoped work-update notifications |
| `capability:manage` | Maintain controlled team capability evidence |
| `organisation:create` | Create a reviewed unit |
| `organisation:edit` | Change reviewed unit metadata |
| `organisation:reparent` | Move a subtree through a reviewed command |
| `organisation:restructure` | Merge, split or deactivate with dispositions |
| `grant:manage` | Create or revoke grants within the grantable ceiling |
| `grant:delegate` | Create a bounded temporary child grant |

An action never implies another action. Descendant scope applies only when the
grant explicitly enables it, and each final service or transaction revalidates
the complete current grant lineage.

## Calendar and workforce records

| Record | Purpose | Important invariants |
| --- | --- | --- |
| `working_patterns` | Effective weekly working intervals | One person, one home leaf, 15-minute arithmetic and bounded validity |
| `calendar_events` | Canonical personal, manager, team, task or imported event | Timed or all-day half-open interval, time zone, privacy, status and version |
| `calendar_event_scopes` | Projection audience | Owner-global, home-unit or explicit team participant |
| `calendar_event_exceptions` | One occurrence change or cancellation | Stable series plus occurrence key, version and immutable command evidence |
| `calendar_event_versions` | Redacted immutable event history | No note text in audit/outbox evidence |
| `calendar_event_commands` | Idempotent event mutation journal | Actor plus idempotency key uniquely identify a command |
| `capacity_exceptions` | Temporary policy reduction | Bounded minutes or percentage with an effective interval |
| `assignment_competencies` | Verified analyst capability | Controlled capability, proficiency, verifier and validity |

Calendar events are stored once. Personal, team and ancestor views are
projections over current membership and current grants. Private notes are not
copied into team views, capacity evidence, prompts, logs, audit events or outbox
payloads.

## Task and package records

| Record | Purpose | Important invariants |
| --- | --- | --- |
| `team_task_ownership` | One owning leaf or triage owner per workflow leg | Ticket, leg, state, topology/policy snapshot and monotonically increasing version |
| `team_task_ownership_history` | Immutable ownership and transfer history | Preserves prior owner and reviewed command evidence |
| `canonical_work_packages` | Individually accountable units of work | Same ticket/leg/leaf, one owner when active, effort, deadline and state |
| `work_package_participants` | Accountable and contributor lifecycle | Active human Analyst with one eligible posting in the owning leaf |
| `work_package_dependencies` | Directed package prerequisites | Same ticket/leg/leaf, no self edge and no cycle |
| `work_package_history` | Immutable package snapshots | Version advances with each reviewed mutation |
| `work_package_commands` | Actor-scoped idempotent package command | Request hash prevents identity reuse with different content |
| `work_package_handovers` | Same-leaf accountable-owner handover | Authoritative ticket assignment, package, participant and reservation binding |

The ticket aggregate remains authoritative for workflow audience. Package
participation cannot manufacture ticket access, ACG access or product access.

## Demand, recommendation and capacity records

| Record | Purpose | Important invariants |
| --- | --- | --- |
| `assignment_demand_estimates` | Versioned route, capability, effort and deadline demand | Bounded range, provenance, expiry and immutable request hash |
| `assignment_recommendations` | Persisted deterministic recommendation snapshot | Input versions, expiry, policy release and state |
| `assignment_recommendation_candidates` | Ranked eligible teams or analysts | Stable rank, safe reasons and deterministic UUID tie-break |
| `assignment_demand_holds` | Expiring team-level planning hold | Never acts as a second personal capacity ledger |
| `assignment_recommendation_decisions` | Manager acceptance or reasoned soft override | Actor, reviewed version, decision and immutable evidence |
| `capacity_reservations` | Sole personal-capacity reservation ledger | One person/package interval, 15-minute minutes, lifecycle and actor-bound replay |

Hard eligibility failures, including inactive account, wrong home leaf, missing
ticket audience, expired capability, insufficient clearance/ACG authority or
unknown capacity, cannot be overridden. Ordinary responses use coarse safe
reason codes and do not reveal another person's calendar, clearance, caveats or
private exclusion details.

## Privacy and retention

- Calendar notes and sensitive exclusion details stay in their authoritative
  object and are omitted from derived operational evidence.
- Ancestor calendar and board views apply small-cohort and complementary
  suppression before returning counts.
- Historical views use current access policy. Historical membership or topology
  never restores revoked access.
- Immutable command, history, audit and outbox records are retained according to
  the repository retention policy. Operational projections can be rebuilt only
  from authorised canonical sources.
- Logical backup and restore include the complete bounded record graph. Restore
  validation must not reinstate a revoked account, grant, ACG or ticket
  relationship.

## Operational interpretation

`disabled` preserves the established application. `shadow` maintains and
compares relational evidence without using it for decisions. `management`
enables reviewed administration and canonical workspace features without
switching live workflow authority. `active` is a release-gated target and must
remain unavailable until the cutover manifest, protected checks and independent
approvals are bound to the exact candidate.
