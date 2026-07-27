# ADR 0043: Separate Shared JIOC Review from Manager Oversight

Status: Accepted

Date: 23 July 2026

## Context

The active deterministic JIOC Agent can route routine eligible work without
mandatory human approval. Existing documentation still described the JIOC
Manager as the decision gate, even though code grants both JIOC Team Members and
Managers the human review and dispute permissions. Managers alone have
whole-flow oversight and intervention authority.

Agent evidence was available through the API but was not consistently visible
in the queue or oversight interface. The evidence score was also liable to be
misread as a confidence probability.

## Decision

1. Human route exceptions remain a shared JIOC reviewer responsibility. Team
   Members are the primary queue role, and Managers may perform the same review.
2. The Manager is an on-loop supervisor for routine Agent decisions, with a
   default attention view and explicit hold, resume and send-to-review controls.
3. Agent decisions expose disposition, recommended route, policy version,
   rationale codes, time and a decimal evidence score. The interface states that
   the score is not a calibrated probability.
4. Oversight links a selected exception into the queue without widening
   permissions.
5. Managers receive aggregate operational evidence, not `audit:read`.
6. Automatic clarification builds the customer hand-off from the final policy
   result so required questions cannot be omitted.
7. Manager intervention responses expose only ticket identity, state and
   version. This intentional pre-release contract correction replaces the
   over-broad full-ticket response and prevents workflow content disclosure.

## Consequences

- Routine routing is not slowed by a redundant Manager approval.
- Exception coverage can be distributed across Team Members and Managers.
- Manager intervention remains explicit, reasoned and auditable.
- Clients of the intervention endpoint must consume its dedicated bounded
  response rather than a full routing-ticket representation.
- Documentation must use "human JIOC reviewer" where either role is authorised.
- Tests and seeded personas must preserve the role boundary.

Companion records: [specification](../specs/jioc-operating-model-and-manager-journey.md),
[operating model](../architecture/JIOC_OPERATING_MODEL.md) and
[threat model](../threat-model/jioc-workflow-restructure.md).
