# ADR 0039: Protected Workflow Draft Authorisation

## Status

Accepted on 18 July 2026.

## Context

The workflow preview path treats `PRODUCT_APPROVE` as manager content authority
without confirming route and audience, and treats `TICKET_READ_ALL` as
administrator content authority. Both shortcuts reach protected draft bytes.
They conflict with Coeus's object-aware ACG and clearance model.

## Decision

1. One product-submission access boundary resolves the live ticket, version and
   asset before authorising any workflow-draft byte or extracted-text read.
2. Ordinary access requires active identity, `PRODUCT_READ`, sufficient
   clearance, active ACG overlap, an allowed workflow state and an exact current
   relationship.
3. Assigned analysts may preview their active work. Named QC reviewers may
   preview QC and rework states.
4. RFA and CM managers are area-wide within their own route kind under ADR
   0023. Manager preview requires `PRODUCT_APPROVE`, the approved route's
   specific permission and a valid active selected-team assignment of that
   route kind. `PRODUCT_APPROVE` alone grants no content access.
5. `TICKET_READ_ALL` permits administrative ticket visibility, not ordinary
   workflow-draft content access.
6. Platform administrators are denied ordinary preview even though their role
   aggregates broad permissions.
7. No workflow-draft emergency endpoint is added until a separate spec decides
   whether clearance, ACG and workflow-state controls may be overridden. Any
   future endpoint must be CSRF protected, reasoned and audited before bytes are
   disclosed.
8. Denial is non-enumerating and occurs before object storage access.

## Consequences

- Admin support cannot inspect workflow-draft content through the ordinary
  preview route.
- Manager preview follows the same route meaning as manager approval without
  incorrectly requiring membership in every selected team.
- Access evaluation needs the selected version and live ACG repository, which
  slightly increases service dependencies but removes incomplete permission
  shortcuts.
- A later break-glass feature requires an explicit product decision and cannot
  be introduced as an implicit administrator branch.

## Rejected Alternatives

- UUID secrecy: identifiers are routing data, not authority.
- `PRODUCT_APPROVE` plus state: it crosses RFA and CM route boundaries.
- Ordinary administrator access: platform administration is not need-to-know
  content authority.
- Reusing Store break-glass automatically: Store and pre-release workflow
  content have different lifecycle and override decisions.
