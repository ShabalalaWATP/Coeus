# ADR 0023: Area teams, JIOC oversight and delegated ACG governance

## Status

Accepted, 2026-07-12.

## Context

Assignments previously carried an optional team display name. Candidate lookup
was route-wide, so a manager with multiple teams could select one team's label
while assigning a member of another. Route permissions also made team ownership
implicit. JIOC owned the routing decision but had no whole-process operational
view after hand-off.

## Decision

- Persist the selected organisational team ID on each analyst assignment and
  derive its name from the team repository.
- Treat RFA Manager and CM Manager as area managers for their respective team
  kind. They may choose any active team of that kind, then only assign active
  members of that selected team.
- Persist ticket ownership through its active route assignments. Manager queue,
  reassignment and approval must agree with the route area and selected team.
- Add a bounded JIOC oversight projection for state, route, team, analyst and
  task-load counts. It is read-only and does not expose product bodies, draft
  content or analyst notes.
- Store ACG administrator identities separately from ACG member identities,
  with an atomic limit of eight active administrators per group. Administration
  grants application-review authority, not product visibility.
- Give every active authenticated user a self-service ACG catalogue and
  application workflow. ACG administrators and platform administrators can
  decide requests for their groups, with self-decision prohibited and approval
  atomically adding membership.
- Keep the current single-writer local runtime. These ownership rules do not
  imply multi-replica support.

## Consequences

- Assignment requests change from a team name to a team ID and OpenAPI clients
  must be regenerated.
- Legacy assignments without a team ID remain readable and are resolved through
  their stored name where an unambiguous team exists.
- Adding another team within an area no longer creates cross-team candidate or
  availability ambiguity.
- JIOC gains operational awareness without gaining workflow mutation authority.
- ACG membership no longer depends exclusively on platform or Store Manager
  intervention, while need-to-know access remains an explicit, audited human
  decision.
