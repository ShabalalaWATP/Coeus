# User and Workflow Views

Status: **implemented**, except where a limitation is called out. Verified
against `e44b66b6` on 23 July 2026.

This page shows Istari from the perspective of people and outcomes. The
[canonical workflow guide](../ARCHITECTURE_WORKFLOW.md) remains authoritative
for ticket states; this page explains how those states are projected to users
and how authority moves between roles. The [Exhaustive Workflow State
Reference](WORKFLOW_STATE_REFERENCE.md) includes every allowlisted transition.

## 1. People, responsibilities and workspaces

Eleven account roles exist. Pending registrant, requester, collaborator and
delegated ACG administrator are relationships or responsibilities, not extra
roles. Accounts may hold several roles; permissions are unioned, but live
separation-of-duties checks still apply.

```mermaid
flowchart LR
    accTitle: Istari people and workspace landscape
    accDescr: Account roles, non-role responsibilities and the deterministic JIOC Agent mapped to customer, routing, delivery, Store and governance workspaces.

    subgraph entry["Entry and request ownership"]
        REG["Pending registrant<br/>non-role persona"]
        C["Customer<br/>Requests, Store, Access Groups, My Team"]
        COLLAB["Ticket collaborator<br/>viewer or editor relationship"]
    end

    subgraph routing["Routing and oversight"]
        JA["DETERMINISTIC<br/>JIOC Agent"]
        JT["JIOC Team Member<br/>JIOC Queue"]
        JM["JIOC Manager<br/>JIOC Oversight, Queue, Admin Analytics"]
    end

    subgraph delivery["Delivery teams"]
        RM["RFA Manager<br/>RFA Queue, Products, Analytics"]
        RT["RFA Team Member<br/>RFA Products"]
        CM["CM Manager<br/>Collection Queue, Products, Analytics"]
        CT["CM Team Member<br/>Collection Products"]
        AN["Analyst<br/>Analyst Workbench"]
        QC["Quality Control Manager<br/>QC Queue"]
    end

    subgraph storegov["Store and platform governance"]
        SM["Intelligence Store Manager<br/>Store, ACG administration"]
        AD["Administrator<br/>all workspaces"]
        DA["Delegated ACG administrator<br/>group responsibility, not a role"]
    end

    REG -->|"administrator approves"| C
    C --> COLLAB
    C -->|"new tasking consent"| JA
    JA -->|"eligible RFA route"| RM
    JA -->|"eligible CM route"| CM
    JA -->|"explicit review or exception"| JT
    JA -.->|"routine oversight"| JM
    JT -->|"human RFA decision"| RM
    JT -->|"human CM decision"| CM
    JM -->|"review or intervention"| RM
    JM -->|"review or intervention"| CM
    RM --> AN
    CM --> AN
    AN --> QC
    QC -->|"released product"| C
    RT -->|"team product stewardship"| RM
    CT -->|"team product stewardship"| CM
    SM -->|"catalogue and access scope"| QC
    AD -->|"platform policy"| SM
    AD -->|"delegates group review"| DA
    DA -->|"application decisions only"| C
```

Delegated ACG administration alone grants no content access. Store browse-all
removes the search-first presentation constraint, not clearance, ACG, status or
draft-audience policy.

## 2. Role-to-workspace summary

| Role                       | Default workspace   | Primary authority                                            |
| -------------------------- | ------------------- | ------------------------------------------------------------ |
| Administrator              | Admin               | Accounts, roles, configuration, all platform permissions     |
| Customer                   | Requests            | Own request, product decisions, new-tasking consent, outcome |
| JIOC Team Member           | JIOC Queue          | Exception routing and dispute adjudication                   |
| JIOC Manager               | JIOC Oversight      | Oversight, hold/resume/intervention and global aggregates    |
| RFA Manager                | RFA Queue           | RFA assignment, manager approval, team and analytics         |
| RFA Team Member            | RFA Products        | Scoped team product stewardship                              |
| CM Manager                 | Collection Queue    | Collection assignment, manager approval, team and analytics  |
| CM Team Member             | Collection Products | Scoped team product stewardship                              |
| Intelligence Store Manager | Store               | Catalogue, product and ACG membership administration         |
| Analyst                    | Analyst Workbench   | Assigned work packages and immutable draft versions          |
| Quality Control Manager    | QC Queue            | QC claim, human checklist, release or rejection              |

The frontend uses permission-based navigation. Backend services, object policy
and commit-time authority are the enforcement boundaries.

## 3. Customer-visible journey and internal projection

The customer sees a small stable journey rather than raw enum names. Several
operational states map to one visible phase.

```mermaid
flowchart TB
    accTitle: Customer-visible request journey mapped to internal workflow phases
    accDescr: Seven customer-facing stages each expand into one or more internal ticket states and staff activities.

    I["1. Intake<br/>describe, correct, submit"]
    S["2. Search<br/>existing products and active work"]
    R["3. Routing<br/>RFA or collection decision"]
    C["4. Collection<br/>optional collection production"]
    A["5. Assessment<br/>analyst production and manager review"]
    Q["6. Quality<br/>QC claim, preflight and release"]
    D["7. Delivery<br/>accept, feedback or request re-analysis"]

    I --> S --> R
    R -->|"RFA route"| A
    R -->|"CM route"| C
    C -->|"CM production completes"| Q
    Q -->|"raw collect release"| D
    Q -->|"analysed collect starts RFA leg"| A
    A --> Q --> D

    I1["DRAFT_INTAKE<br/>INFO_REQUIRED"]
    S1["RFI_SEARCHING, OFFERED or INCOMPLETE<br/>ACTIVE_WORK_REVIEW, NEW_TASKING_CONSENT"]
    R1["JIOC_ROUTING_PENDING<br/>JIOC_REVIEW or HOLD"]
    C1["COLLECT_CHOICE<br/>CM assignment and production"]
    A1["ANALYST_ASSIGNMENT, IN_PROGRESS<br/>MANAGER_APPROVAL"]
    Q1["QC_REVIEW<br/>REWORK_REQUIRED"]
    D1["DISSEMINATION_READY<br/>outcome and re-analysis states"]

    I -. projects .-> I1
    S -. projects .-> S1
    R -. projects .-> R1
    C -. projects .-> C1
    A -. projects .-> A1
    Q -. projects .-> Q1
    D -. projects .-> D1
```

Closed outcomes include accepted existing product, joined existing work,
unanswered/declined tasking, requirement met, re-analysis declined, delivered
compatibility closure and cancellation.

## 4. Principal authority hand-offs

This is an authority narrative, not an HTTP trace. The technical request and
transaction sequence is in
[Application components](APPLICATION_COMPONENTS.md#4-request-execution-and-commit-boundary).

```mermaid
sequenceDiagram
    accTitle: Principal human and deterministic authority hand-offs
    accDescr: A customer request moves through deterministic intake and search, JIOC routing, delivery management, analysts, quality control and customer outcome.
    autonumber

    actor C as Customer
    participant SYS as Deterministic controllers
    participant JA as JIOC Agent
    actor J as JIOC human
    actor RM as RFA manager
    actor CM as CM manager
    actor A as Assigned analyst
    actor Q as QC manager

    C->>SYS: Describe, correct and submit requirement
    SYS-->>C: Authorised product offers or bounded retry state
    alt product accepted
        C->>SYS: Accept product and close
    else no accepted product
        SYS-->>C: Visible matching work or new-tasking consent
        alt join visible work
            C->>SYS: Join and close duplicate request
        else create new work
            C->>SYS: Explicitly consent
            SYS->>JA: Versioned evidence and capability reviews
            alt eligible deterministic RFA route
                JA->>RM: Commit RFA route
            else eligible deterministic CM route
                JA->>CM: Commit CM route
            else clarification
                JA-->>C: Ask bounded clarification
            else exception
                JA->>J: Refer explicit human review
                alt human selects RFA
                    J->>RM: Commit reviewed RFA route
                else human selects CM
                    J->>CM: Commit reviewed CM route
                end
            end
            opt a delivery route is committed
                alt RFA production leg
                    RM->>A: Assign one to five eligible analysts
                    A->>RM: Submit immutable assessed-product manifest
                    alt RFA manager returns work
                        RM-->>A: Reasoned rework
                    else RFA manager approves
                        RM->>Q: Place exact version into QC
                        Q->>Q: Claim, preflight and human checklist
                        alt QC rejects
                            Q-->>A: Return to assigned analyst loop
                        else QC releases
                            Q-->>C: Publish controlled product
                            C->>SYS: Accept outcome or request re-analysis
                        end
                    end
                else CM production leg
                    CM->>A: Assign one to five eligible analysts
                    A->>CM: Submit immutable collection manifest
                    alt CM manager returns work
                        CM-->>A: Reasoned rework
                    else CM manager approves
                        CM->>Q: Place exact collect into QC
                        Q->>Q: Claim, preflight and human checklist
                        alt QC rejects
                            Q-->>A: Return to assigned analyst loop
                        else analysed collection
                            Q->>RM: Forward completed collect to RFA assignment
                            RM->>A: Assign follow-up assessment
                            A->>RM: Submit assessed-product manifest
                            alt RFA manager returns assessment
                                RM-->>A: Reasoned follow-up rework
                            else RFA manager approves assessment
                                RM->>Q: Place exact RFA version into QC
                                Q->>Q: Claim, preflight and human checklist
                                alt QC rejects assessment
                                    Q-->>A: Return to assigned analyst loop
                                else QC releases assessment
                                    Q-->>C: Release assessed product
                                    C->>SYS: Accept outcome or request re-analysis
                                end
                            end
                        else raw collection
                            Q-->>C: Release controlled collect
                            C->>SYS: Accept outcome or request re-analysis
                        end
                    end
                end
            end
        end
    end
```

The Routing Critic is advisory after a route is committed. It never delays or
changes the route. A JIOC Manager is on the loop for routine automation and in
the loop for holds, intervention and exceptions.

## 5. Outcome variants

```mermaid
flowchart LR
    accTitle: Implemented request outcome variants
    accDescr: Five implemented branches show how product reuse, joined work, RFA, raw collection and collection plus analysis reach closure.

    START["Submitted requirement"]
    PRODUCT["Existing authorised product"]
    WORK["Visible active work"]
    RFA["New RFA task"]
    RAW["New raw collection task"]
    BOTH["Collection plus RFA analysis"]

    PEND["Customer accepts<br/>CLOSED_EXISTING_PRODUCT_ACCEPTED"]
    JOIN["Customer joins<br/>CLOSED_JOINED_EXISTING_WORK"]
    RPROD["Analyst, manager, QC<br/>released assessed product"]
    CPROD["Collector/analyst, manager, QC<br/>released raw collect"]
    APROD["CM production and QC forwarding<br/>then RFA production and QC release"]

    START --> PRODUCT --> PEND
    START --> WORK --> JOIN
    START --> RFA --> RPROD
    START --> RAW --> CPROD
    START --> BOTH --> APROD
```

## 6. Holds, rework and re-analysis

```mermaid
flowchart TB
    accTitle: Workflow exception and rework loops
    accDescr: Search degradation, clarification, routing holds, manager rework, QC rework and disputed re-analysis return to controlled earlier stages.

    SEARCH["Search coverage incomplete"]
    RETRY["Customer-triggered retry"]
    INFO["Information required"]
    ROUTE["JIOC routing or review"]
    HOLD["JIOC intervention hold<br/>stores exact previous state"]
    ASSIGN["Analyst assignment or production"]
    MREV["Manager approval"]
    QREV["QC review"]
    REWORK["Rework required<br/>named reviewer retained"]
    DELIVERY["Customer outcome"]
    MANAGER["Manager re-analysis review"]
    JIOC["Independent JIOC adjudication"]
    CLOSED["Requirement met or re-analysis declined"]

    SEARCH --> RETRY -->|"complete"| ROUTE
    ROUTE -->|"clarification"| INFO -->|"requester resumes"| ROUTE
    ROUTE --> HOLD -->|"resume exact state"| ROUTE
    HOLD -->|"send to review"| ROUTE
    ROUTE --> ASSIGN --> MREV
    MREV -->|"return"| ASSIGN
    MREV -->|"approve exact manifest"| QREV
    QREV -->|"reject"| REWORK -->|"new immutable version"| QREV
    QREV -->|"release"| DELIVERY
    DELIVERY -->|"accept"| CLOSED
    DELIVERY -->|"request re-analysis"| MANAGER
    MANAGER -->|"agree"| ASSIGN
    MANAGER -->|"disagree"| JIOC
    JIOC -->|"order re-analysis"| ASSIGN
    JIOC -->|"decline"| CLOSED
```

Cancellation is permitted only from the allowlisted non-terminal states in
`domain/state_machine.py`. The canonical state diagram intentionally shows the
principal flow; code remains authoritative for exhaustive transitions.

## Sources and companion records

| Concern                      | Authority                                                                                                  |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Roles and default workspaces | `apps/api/src/coeus/domain/auth.py`, `domain/rbac.py`, `apps/web/src/app/route-policy.ts`                  |
| Ticket transitions           | `apps/api/src/coeus/domain/state_machine.py`                                                               |
| Exhaustive transition views  | [Workflow State Reference](WORKFLOW_STATE_REFERENCE.md)                                                    |
| Customer projection          | `apps/api/src/coeus/services/customer_status.py`                                                           |
| Assignment and approval      | `analyst_assignment_service.py`, `manager_approval.py`, `quality_control.py`, `customer_outcomes.py`       |
| User guidance                | [Roles and User Stories](../ROLES_AND_USER_STORIES.md), [User Guide](../USER_GUIDE.md)                     |
| Feature contract             | [External product and customer acceptance](../specs/external-product-ingestion-and-customer-acceptance.md) |
