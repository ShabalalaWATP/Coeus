# Organisation Administration Guide

Use this guide for the Sprint 24 management workspace. These controls are
available only in the supported local/test management mode until an authorised
cutover makes the relational hierarchy operational.

Related references:

- [Organisation and workforce data dictionary](../architecture/ORGANISATION_AND_WORKFORCE_DATA_DICTIONARY.md)
- [Sprint 24 feature contract](../specs/hierarchical-teams-workforce-calendars-and-task-boards.md)
- [Projection and capacity repair](organisation-projection-and-capacity-repair.md)
- [Threat model](../threat-model/hierarchical-teams-workforce-calendars-and-task-boards.md)

## Safety rules

1. Preview every structural or workforce command and review the complete impact
   before confirming it.
2. Never use hierarchy membership as evidence of clearance, ACG membership,
   ticket audience or product access.
3. Keep every person in one effective home unit. Transfer work separately when
   work must move without moving a person.
4. Treat stale-preview, changed-version and changed-grant errors as a request to
   start a new preview. Do not retry with copied hashes.
5. Stop when the readiness panel reports a blocker. The panel cannot approve or
   activate a cutover.

## Open the management workspace

1. Sign in as a platform administrator or manager with explicit organisation
   and workspace grants.
2. Open **Administration**, then **Organisation**.
3. Select a unit in the tree. Breadcrumbs show the selected path.
4. Check whether each badge is direct or inherited. Inherited authority is
   action-specific and applies to descendants only when the grant says so.

An inaccessible identifier returns the same safe response as an absent one.
Administrators should investigate through audited readiness or repair tools,
not by probing identifiers in the browser.

## Create the first root

The bootstrap action is a one-time empty-install ceremony.

1. Confirm that the organisation store is empty.
2. Supply the deployment bootstrap nonce.
3. Re-enter the current administrator password.
4. Preview the root, initial grant ceiling and permanent bootstrap marker.
5. Confirm once. A second bootstrap attempt is denied even with a new nonce.

Do not use bootstrap to repair an existing hierarchy. Use reconciliation or an
explicit reviewed lifecycle command.

## Create or edit a unit

1. Select the intended parent.
2. Choose **Create unit**, or choose **Edit** on the selected unit.
3. Enter a bounded name, short name, category, time zone and description.
4. For a delivery leaf, configure its route, WIP limit and controlled
   capability coverage separately.
5. Preview. Check the parent, topology revision and affected grants.
6. Confirm using the current preview.

A unit cannot parent itself, exceed depth 12 or create a cycle. Delivery
authority is explicit and does not flow from a unit label.

## Reparent a subtree

1. Select the subtree root and choose **Reparent**.
2. Select the new parent from the authorised destination scope.
3. Review descendant count, new paths, affected grants, workforce, calendars
   and work ownership.
4. Resolve every blocking disposition before confirming.
5. Confirm the exact preview.
6. Verify that obsolete descendant authority disappears immediately.

Do not restore old route-wide authority after reparenting. If the command fails
after review, create a fresh preview because topology and authority versions may
have changed.

## Merge, split or deactivate

These commands require an explicit disposition for every named object.

### Merge

- Choose an existing successor.
- Review child-subtree movement, memberships, grants, profiles, capabilities,
  pending transfers and active workflow ownership.
- Move, complete or cancel work explicitly. No implicit orphaning is allowed.

### Split

- Define at least two successors.
- Map every child, membership, grant, delivery policy, task and pending transfer
  to exactly one valid outcome.
- Preserve fixed-term membership bounds and immutable history.

### Deactivate

- Remove or disposition active memberships, grants, work, reservations,
  delivery profiles and child units first.
- A unit with unresolved active evidence cannot be deactivated.

## Manage grants

1. Select the manager and root unit.
2. Choose one action from the controlled action dictionary.
3. Decide whether that action applies only to the root or also to descendants.
4. Set a bounded validity interval for temporary delegation.
5. Preview the source grant, delegation depth and grantable ceiling.
6. Confirm.

Revoking one grant leaves another valid independent grant intact. Revoking or
expiring a source invalidates its descendants. Suspending a human grantor or
holder also invalidates the lineage. Services are recognised only from the
code-registered service-principal allowlist.

## Manage personnel

### Add a posting

- Select the direct home unit.
- Choose a membership role and effective interval.
- Mark assignment eligibility only for an active Analyst posting in a delivery
  leaf.
- Preview and confirm.

### Suspend or end a posting

- Suspension stops assignment eligibility immediately but preserves history.
- Ending requires an explicit end time and dispositions for unresolved work.
- Account suspension is independent and also removes assignment eligibility.

### Transfer a person

1. Select source and target units.
2. Choose one exact effective instant.
3. Review work, future manager events and reservations.
4. Provide every required disposition.
5. Confirm.

The source interval ends exactly when the target interval starts. The target
does not grant early access. Concurrent or overlapping second postings are
rejected by both service and database boundaries.

## Manage calendars and capacity

- Users manage personal events from **My profile**, then **Calendar**.
- Managers may create manager-owned commitments only with `calendar:manage`.
- A manager cannot edit an owner-created personal event.
- Private notes remain hidden from team projections and operational evidence.
- Team views require `calendar:view_availability`; named detail requires the
  separate `calendar:view_detail` action.
- Ancestor views suppress small or incomplete cohorts rather than inferring a
  value.

Calendar, working-pattern and reservation changes affect forecasts from the
same canonical records. Do not copy events into separate team calendars.

## Review team work

The workspace board is a projection of ticket workflow and canonical ownership.
It is not a second state machine.

- `task:view` permits the bounded board.
- `task:assign` permits reviewed package planning and capacity reservation.
- `task:transfer` permits the separate controlled work-transfer workflow.
- Package contributors and dependencies use dedicated previewed commands.
- Same-leaf accountable handover moves a package, not a person.

Every object link rechecks its own policy. Seeing a package card never grants
ticket, Store product or asset access.

## Inspect readiness

Open **Cutover readiness** to see plain-language database evidence. Technical
identifiers are collapsed by default. The report is read-only and checks the
migration head, topology, identity projection, findings, ownership, packages,
reservations, routing mappings and the scoped JIOC service grant.

The report cannot record approval or change runtime mode. Protected CI,
security review, routing approval and an explicit cutover decision remain
separate release evidence.

## Recover safely

- Use the [repair runbook](organisation-projection-and-capacity-repair.md) for a
  bounded read-only report and narrowly safe reservation repair.
- Do not edit immutable histories, audit events, command journals or outbox
  records directly.
- Take a coordinated logical backup before an approved structural cutover.
- After restore, replay current account, grant, ACG and ticket revocations before
  permitting access. A restore must never make revoked authority valid again.
- Prefer forward repair after an authority cutover. Do not re-enable legacy
  route-wide authority as rollback.

## Audit checklist

For each administrative change record:

- actor and current account state;
- selected unit and exact action;
- direct or descendant scope;
- preview and execution command identities;
- versions and authority lineage;
- reason and explicit dispositions;
- audit and outbox result; and
- post-command readiness or drift result when relevant.
