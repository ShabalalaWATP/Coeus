# Threat Model: RFA And CM Routing

## Scope

Sprint 8 RFA and CM capability reviews, manager queues, approval, rejection,
clarification, override decisions and ticket-level workflow-plan updates.

## Assets

- Customer ticket intake and timeline.
- RFA and CM capability-review outputs.
- Manager decisions and audit events.
- Workflow-plan update records.

## Threats And Controls

- Similar-request workflow reads accept the same JIOC, RFA and collection review permissions
  as the routing queues. This keeps object-level scope consistent while preventing a JIOC
  reviewer from receiving a false not-found response for a ticket already visible in their queue.

| Threat | Control in Sprint 8 |
|---|---|
| A customer invokes manager-only route actions. | Routing queues and actions require RFA or collection review permissions and return 403 or 404 where appropriate. |
| An agent routes a ticket directly to analysts without human approval. | Capability checks only move tickets to manager review or clarification. `ANALYST_ASSIGNMENT` requires manager approval. |
| RFA failure drops a viable collection task. | Routing runs both reviews and explicitly falls back to CM when RFA cannot satisfy and CM can. |
| Manager override hides why the recommendation was bypassed. | Override approval requires a reason and records a `manager_override` audit event. |
| Ambiguous requirements reach analysts. | Neither-capable or manager clarification paths move the ticket to `INFO_REQUIRED` with focused questions. |
| Failed audit persistence leaves a hidden route transition behind. | Route review, approval, rejection and clarification restore the original ticket state if audit recording fails after the proposed ticket update. |
| Route reviews leak unauthorised product details. | Sprint 8 routing operates on ticket intake and prior RFI search outcomes, not product detail payloads. |

## Residual Risk

- The deterministic agents are synthetic heuristics for local development. They
  are not a real capability model.
- Ticket-level workflow-plan updates are stored with the ticket until a
  dedicated planning workspace is specified.
- Analyst assignment itself is deferred to Sprint 9.

## July 2026 decision safeguards

- JIOC approval remains unavailable until both capability reviews and the
  current route recommendation exist.
- Ticket selection and all decision controls lock during a write, preventing a
  response for one ticket being applied to another ticket selected mid-flight.
- Managers can inspect submitted work before deciding, while separation of
  duties remains enforced specifically for approval.
