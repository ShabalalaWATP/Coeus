# JIOC Operating Model and Manager Journey

Status: Implemented

Last verified: 23 July 2026

## Objective

Align implementation, tests and documentation with the active deterministic
JIOC Agent. Preserve shared human exception authority while making the JIOC
Manager's on-loop oversight role explicit and operationally useful.

## Requirements

- Treat the JIOC Agent as a system service, not an assignable RBAC role.
- Preserve `jioc:review` and dispute authority for Team Members and Managers.
- Reserve whole-flow oversight and intervention for Managers.
- Display policy version, route, evidence score and rationale codes without
  presenting the score as a probability.
- Default oversight to attention items and allow direct navigation to a selected
  exception in the JIOC queue.
- Require reasons for overrides, rejection, clarification and intervention.
- Deliver final policy clarification questions to the customer.
- Seed distinct Team Member and Manager personas for end-to-end role testing.
- Keep raw audit-log access outside both JIOC roles.

## Acceptance evidence

- Backend tests cover automatic clarification and Team Member versus Manager
  permission boundaries.
- Frontend tests cover Agent evidence, attention filtering, deep linking and
  intervention feedback.
- The canonical architecture guide includes responsibility, routing, exception,
  Manager, intervention and dispute views.

Companion records: [ADR 0043](../adr/0043-jioc-human-review-and-manager-oversight.md),
[operating model](../architecture/JIOC_OPERATING_MODEL.md) and
[threat model](../threat-model/jioc-workflow-restructure.md).
