# Threat Model: RFA And CM Routing

## Scope

Sprint 8 RFA and CM capability reviews, manager queues, approval, rejection,
clarification, override decisions and ticket-level project-plan updates.

## Assets

- Customer ticket intake and timeline.
- RFA and CM capability-review outputs.
- Manager decisions and audit events.
- Project-plan update records.

## Threats And Controls

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
- Ticket-level project-plan updates are not yet persisted to a database-backed
  project workspace.
- Analyst assignment itself is deferred to Sprint 9.
