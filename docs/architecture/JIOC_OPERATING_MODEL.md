# JIOC Operating Model and Journeys

Status: Current implementation

Last verified: 23 July 2026

Primary owners: JIOC operations and platform engineering

This guide separates the deterministic JIOC Agent service from the two human
JIOC account roles. It is the canonical description of routing responsibility,
exception handling and Manager oversight. State names are defined in the
[workflow state reference](WORKFLOW_STATE_REFERENCE.md).

## Responsibility model

The Agent is a system principal, not a role that can be assigned to a person.
Both human roles can review exceptions and adjudicate referred disputes. The
Manager additionally supervises the whole flow and can intervene.

| Capability | JIOC Agent | JIOC Team Member | JIOC Manager |
| --- | --- | --- | --- |
| Evaluate versioned routing evidence | Runs policy | Inspects evidence | Inspects evidence and trends |
| Apply a routine eligible route | Yes, in active mode | Yes, from review | Yes, from review |
| Request required clarification | Yes, through a customer hand-off | Yes | Yes |
| Decide an exception or override | Refers only | Yes, reason required for an override | Yes, reason required for an override |
| Adjudicate a referred re-analysis dispute | No | Yes, subject to independence checks | Yes, subject to independence checks |
| See whole-flow oversight | No | No | Yes |
| Hold, resume or send eligible work to review | No | No | Yes |
| Read the raw audit log | No | No | No |

```mermaid
flowchart LR
    accTitle: JIOC responsibility and authority
    accDescr: The deterministic JIOC Agent routes routine work. Team Members and Managers share exception review, while only Managers have whole-flow oversight and intervention authority.

    C["Customer"]
    A["JIOC Agent<br/>system service"]
    H["Human JIOC reviewer"]
    T["JIOC Team Member<br/>review and disputes"]
    M["JIOC Manager<br/>review, disputes, oversight<br/>and intervention"]
    R["RFA or CM team"]

    C -->|"consent and clarified requirement"| A
    A -->|"routine route"| R
    A -->|"questions"| C
    A -->|"abstention or policy exception"| H
    T --> H
    M --> H
    H -->|"approved or overridden route"| R
    M -.->|"on-loop supervision"| A
    M -.->|"hold, resume, send to review"| R
```

## End-to-end routing workflow

Active local and test mode uses `jioc-routing-policy-v2`. Hosted activation is a
separate deployment decision. Shadow mode records evidence but refers the case
to human review. Disabled mode also refers the case.

```mermaid
flowchart TB
    accTitle: JIOC routing outcomes
    accDescr: Customer consent enters pending routing. The active deterministic policy either applies one safe route, asks required questions or refers the case to a human JIOC reviewer.

    CONSENT["Customer consents to tasking"]
    PENDING["JIOC_ROUTING_PENDING"]
    EVIDENCE["Snapshot search, offer, requirement,<br/>restriction, capability and capacity evidence"]
    MODE{"Routing mode"}
    POLICY{"Deterministic policy result"}
    RFA["ANALYST_ASSIGNMENT<br/>RFA route"]
    CM["COLLECT_CHOICE<br/>CM route"]
    INFO["INFO_REQUIRED<br/>customer receives questions"]
    REVIEW["JIOC_REVIEW<br/>human JIOC queue"]

    CONSENT --> PENDING --> EVIDENCE --> MODE
    MODE -->|"active"| POLICY
    MODE -->|"shadow or disabled"| REVIEW
    POLICY -->|"one eligible RFA route"| RFA
    POLICY -->|"one eligible CM route"| CM
    POLICY -->|"required questions"| INFO
    POLICY -->|"risk, conflict, restriction,<br/>missing or stale evidence"| REVIEW
    INFO -->|"requester supplies routing clarification"| REVIEW
```

Every Agent decision records its policy version, disposition, recommended route,
evidence score, rationale codes and creation time. The evidence score is a policy
input, not a calibrated probability. A durable outbox intent triggers a
shadow-only Routing Critic; critic output cannot change the route.

## Human exception journey

The shared queue is the Team Member's default workspace. A Manager can use the
same queue when operational cover or escalation requires it.

```mermaid
sequenceDiagram
    autonumber
    accTitle: Human JIOC exception review
    accDescr: A human reviewer inspects the exact agent and capability evidence, then approves, overrides, asks for clarification or rejects the route through an audited command.

    participant Agent as JIOC Agent
    participant Queue as JIOC Queue
    actor Reviewer as Team Member or Manager
    participant API as Routing service
    participant Ticket as Versioned ticket
    actor Customer
    participant Team as RFA or CM team

    Agent->>Ticket: Commit referral and decision evidence
    Ticket-->>Queue: JIOC_REVIEW projection
    Reviewer->>Queue: Open task and inspect policy reasons
    Queue->>API: Submit decision with expected ticket version
    API->>API: Recheck session, jioc:review and live authority
    alt approve recommendation
        API->>Ticket: Commit chosen route
        Ticket-->>Team: Route becomes available
    else override recommendation
        API->>API: Require recorded reason
        API->>Ticket: Commit alternate route and rationale
        Ticket-->>Team: Route becomes available
    else clarification
        API->>API: Require at least one question
        API->>Ticket: Commit INFO_REQUIRED and hand-off
        Ticket-->>Customer: Show required questions
        Customer->>Ticket: Supply routing clarification
        Ticket-->>Queue: Return to JIOC_REVIEW
    else reject
        API->>API: Require recorded reason
        API->>Ticket: Commit INFO_REQUIRED for requester revision
        Ticket-->>Customer: Requester can revise and resubmit
    end
```

Ordinary approval does not require free text. Override, rejection and
clarification do. Optimistic concurrency rejects decisions made against a stale
ticket.

## Manager journey

The Manager starts at JIOC Oversight, not the exception queue. The default
attention view prioritises pending routing, human review and held work. The
Manager can filter all work or Agent-routed work, inspect the exact Agent policy
evidence and open a review case directly in the queue.

```mermaid
flowchart LR
    accTitle: JIOC Manager on-loop operating cycle
    accDescr: The Manager monitors outcome and queue signals, investigates attention items, chooses whether to observe, review or intervene, and verifies the resulting state.

    START["Open JIOC Oversight"]
    SIGNALS["Review state counts,<br/>Agent outcomes and attention list"]
    ITEM["Inspect task, route,<br/>policy and rationale codes"]
    DECIDE{"Action needed?"}
    OBSERVE["Continue on-loop monitoring"]
    REVIEW["Open JIOC Queue<br/>for human review"]
    HOLD["Hold eligible work<br/>with reason"]
    SEND["Send eligible work to review<br/>with reason"]
    RESUME["Resume held work<br/>with reason"]
    VERIFY["Verify state and aggregate signals"]

    START --> SIGNALS --> ITEM --> DECIDE
    DECIDE -->|"no"| OBSERVE --> SIGNALS
    DECIDE -->|"exception decision"| REVIEW --> VERIFY
    DECIDE -->|"pause risk or dependency"| HOLD --> VERIFY
    DECIDE -->|"reconsider routing"| SEND --> VERIFY
    DECIDE -->|"hold condition cleared"| RESUME --> VERIFY
    VERIFY --> SIGNALS
```

Intervention is exceptional and always requires a reason. It is not a second
approval gate for routine Agent routes.

```mermaid
stateDiagram-v2
    accTitle: Manager intervention state changes
    accDescr: A Manager may hold eligible active work, resume it to the exact saved state, or send eligible routing states to human JIOC review.

    state "Holdable active state" as Holdable
    state "Reviewable routing state" as Reviewable
    state "JIOC_INTERVENTION_HOLD" as Hold
    state "JIOC_REVIEW" as Review

    Holdable --> Hold: hold(reason)
    Reviewable --> Hold: hold(reason)
    Hold --> Holdable: resume(reason) to saved state
    Hold --> Reviewable: resume(reason) to saved state
    Reviewable --> Review: send_to_review(reason)
```

The service enforces the exact eligible-state allowlists. The UI cannot broaden
them. Managers see aggregate operational evidence, but do not have `audit:read`
and cannot browse the raw audit log.

## Re-analysis disputes

Post-release disagreement first returns to the responsible RFA or CM Manager.
That manager may resolve it or refer it to a human JIOC reviewer. The final JIOC
adjudicator must not be the requester, assigned analyst or referring manager.

```mermaid
sequenceDiagram
    autonumber
    accTitle: Independent JIOC re-analysis adjudication
    accDescr: A customer dispute goes to the responsible delivery manager and can be referred to an independent JIOC Team Member or Manager before the customer receives the outcome.

    actor Customer
    actor DeliveryManager as RFA or CM Manager
    actor JIOC as Independent JIOC reviewer
    participant Ticket as Versioned ticket

    Customer->>Ticket: Dispute delivered outcome
    Ticket-->>DeliveryManager: Re-analysis review
    alt manager agrees re-analysis is needed
        DeliveryManager->>Ticket: Record agreement and rationale
        Ticket->>Ticket: Return to ANALYST_IN_PROGRESS
        Ticket-->>Customer: Publish only after production and QC complete
    else manager disagrees and refers
        DeliveryManager->>Ticket: Refer with rationale
        Ticket-->>JIOC: JIOC_REANALYSIS_ADJUDICATION
        JIOC->>Ticket: Independence checks and final decision
        Ticket-->>Customer: Publish adjudication
    end
```

## Security and operational boundaries

- Route-changing commands re-evaluate live permissions and relevant authority.
- Workflow writes use expected versions and fail closed on conflicts.
- The Agent is deterministic and cannot invoke arbitrary tools or external
  providers.
- Agent and human decision evidence is content-safe and avoids sensitive free
  text in aggregate oversight.
- Manager intervention does not grant raw audit-log access.
- If active execution cannot safely complete, the expected outcome is human
  review. Pending items remain visible to oversight and durable discovery retries.

## Implementation sources

- Roles and permissions: `apps/api/src/coeus/domain/rbac.py`
- Agent orchestration and evidence: `apps/api/src/coeus/services/jioc_routing_agent.py`
- Policy outcomes: `apps/api/src/coeus/services/jioc_routing_policy.py`
- Human review: `apps/api/src/coeus/services/routing.py`
- Manager intervention: `apps/api/src/coeus/services/jioc_intervention.py`
- Oversight projection: `apps/api/src/coeus/services/routing_oversight.py`
- Re-analysis disputes: `apps/api/src/coeus/services/customer_outcomes.py`
- Current decision: [ADR 0043](../adr/0043-jioc-human-review-and-manager-oversight.md)
- Security boundaries: [JIOC workflow threat model](../threat-model/jioc-workflow-restructure.md)
