# Istari Architecture: Workflow

How a request moves through Istari, where bounded agents make decisions and
where people are in or on the loop. See [Architecture](ARCHITECTURE.md) for the
system structure and [Architecture: Deployment](ARCHITECTURE_DEPLOYMENT.md) for
runtime and cloud boundaries. Every diagram below describes shipped behaviour.

---

## 1. Authority at a glance

| Stage | Automated authority | Human position |
| --- | --- | --- |
| Intake | Deterministic extraction, safety, completeness and contradiction checks control the permitted next action. A model may only select one already-missing field when admitted. | Requester is in the loop: answers, edits, submits or cancels. |
| Existing-product search | Access filtering, baseline retrieval, ranking, assurance and lifecycle outcome are deterministic. The Search Planner may add bounded search wording only. | Requester is in the loop: accepts or rejects offers. |
| Active-work search | Deterministic, access-filtered matching offers visible existing work. | Requester is in the loop: joins existing work or consents to new tasking. |
| JIOC routing | The active deterministic JIOC Agent may choose CM, RFA, clarification or manager review from versioned evidence. | JIOC Managers are on the loop for routine routes, with metrics, hold, reopen and audited intervention. They enter the loop for explicit review and exceptions. |
| Production and release | Assignment, manager approval, QC preflight and release gates are deterministic controls. | Analysts, delivery managers, QC and the requester are in the loop at their respective decisions. |
| Outcome review | No agent decides whether released work met the requirement. | Requester, responsible manager and, on dispute, an independent JIOC human are in the loop. |

No model can change lifecycle state, access control, policy or release authority.

---

## 2. Request lifecycle

The diagram shows the principal transitions. Cancellation and JIOC intervention
can also occur from the allowlisted states defined by the state machine.

```mermaid
stateDiagram-v2
    [*] --> DRAFT_INTAKE: start conversation
    DRAFT_INTAKE --> RFI_SEARCHING: requester submits complete intake
    DRAFT_INTAKE --> INFO_REQUIRED: blocking correction needed

    RFI_SEARCHING --> RFI_MATCH_OFFERED: products offered
    RFI_SEARCHING --> RFI_SEARCH_INCOMPLETE: coverage incomplete
    RFI_SEARCHING --> ACTIVE_WORK_REVIEW: matching work found
    RFI_SEARCHING --> NEW_TASKING_CONSENT: no product or active work
    RFI_SEARCH_INCOMPLETE --> RFI_MATCH_OFFERED: retry finds products
    RFI_SEARCH_INCOMPLETE --> NEW_TASKING_CONSENT: definitive retry finds none
    RFI_MATCH_OFFERED --> CLOSED_EXISTING_PRODUCT_ACCEPTED: requester accepts
    RFI_MATCH_OFFERED --> ACTIVE_WORK_REVIEW: all products rejected, work found
    RFI_MATCH_OFFERED --> NEW_TASKING_CONSENT: all products rejected

    ACTIVE_WORK_REVIEW --> CLOSED_JOINED_EXISTING_WORK: requester joins
    ACTIVE_WORK_REVIEW --> NEW_TASKING_CONSENT: requester continues
    NEW_TASKING_CONSENT --> ACTIVE_WORK_SEARCH_INCOMPLETE: work check incomplete
    ACTIVE_WORK_SEARCH_INCOMPLETE --> ACTIVE_WORK_REVIEW: retry finds work
    ACTIVE_WORK_SEARCH_INCOMPLETE --> NEW_TASKING_CONSENT: retry finds none
    NEW_TASKING_CONSENT --> JIOC_ROUTING_PENDING: requester consents
    NEW_TASKING_CONSENT --> CLOSED_UNANSWERED: requester declines

    JIOC_ROUTING_PENDING --> ANALYST_ASSIGNMENT: agent routes RFA
    JIOC_ROUTING_PENDING --> COLLECT_CHOICE: agent routes CM
    JIOC_ROUTING_PENDING --> INFO_REQUIRED: agent requests clarification
    JIOC_ROUTING_PENDING --> JIOC_REVIEW: agent abstains, shadows, fails or is disabled
    JIOC_REVIEW --> ANALYST_ASSIGNMENT: manager routes RFA
    JIOC_REVIEW --> COLLECT_CHOICE: manager routes CM
    JIOC_REVIEW --> INFO_REQUIRED: manager requests clarification
    COLLECT_CHOICE --> ANALYST_ASSIGNMENT: requester selects collect outcome

    ANALYST_ASSIGNMENT --> ANALYST_IN_PROGRESS: manager assigns analysts
    ANALYST_IN_PROGRESS --> MANAGER_APPROVAL: analysts submit
    MANAGER_APPROVAL --> ANALYST_IN_PROGRESS: manager returns work
    MANAGER_APPROVAL --> QC_REVIEW: manager approves
    QC_REVIEW --> REWORK_REQUIRED: QC rejects
    REWORK_REQUIRED --> QC_REVIEW: analyst resubmits
    QC_REVIEW --> DISSEMINATION_READY: QC releases
    QC_REVIEW --> ANALYST_ASSIGNMENT: analysed collect moves to RFA

    DISSEMINATION_READY --> CLOSED_REQUIREMENT_MET: requester accepts
    DISSEMINATION_READY --> MANAGER_REANALYSIS_REVIEW: requester rejects
    MANAGER_REANALYSIS_REVIEW --> ANALYST_IN_PROGRESS: manager agrees
    MANAGER_REANALYSIS_REVIEW --> JIOC_REANALYSIS_ADJUDICATION: manager disagrees
    JIOC_REANALYSIS_ADJUDICATION --> ANALYST_IN_PROGRESS: JIOC orders re-analysis
    JIOC_REANALYSIS_ADJUDICATION --> CLOSED_REANALYSIS_DECLINED: JIOC closes
```

`JIOC_INTERVENTION_HOLD` is an audited pause. A JIOC Manager can place routing or
delivery states on hold and resume the exact previous state. From routing
pending, collect choice or analyst assignment, they can instead refer the case
to `JIOC_REVIEW`.

---

## 3. End-to-end decision flow

```mermaid
sequenceDiagram
    autonumber
    actor C as Requester
    participant I as Intake controller + planner
    participant S as RFI search + search planner
    participant W as Active-work discovery
    participant J as JIOC Agent
    participant K as Routing Critic
    actor JM as JIOC Manager
    actor M as RFA or CM manager
    actor A as Analysts
    actor Q as QC manager

    C->>I: describe need, correct and submit
    I-->>C: safe local question from admitted bounded advice
    S-->>C: access-filtered product offers or assured no-match
    alt product satisfies the need
        C->>C: accept and close
    else no accepted product
        W-->>C: authorised matching work, if any
        alt join existing work
            C->>C: join and close duplicate request
        else consent to new tasking
            C->>J: consent creates routing-pending ticket
            J->>J: evaluate capability, search, capacity and restrictions
            alt sufficient unambiguous evidence
                J->>M: apply CM or RFA route
            else clarification or exception
                J-->>C: request clarification
                J->>JM: refer explicit review
            end
            J-->>K: commit exact decision and request shadow critique
            K-->>JM: oversight-only coded critique
            JM-->>J: monitor, hold or send eligible case to review
            M->>A: assign one to five analysts
            A->>M: submit draft
            M->>Q: approve, or return for rework
            Q->>C: QC and release, or return for rework
            C->>C: accept outcome or request re-analysis
        end
    end
```

The Routing Critic never delays or changes the committed route. Local/test
runtime records its best-effort critique after routing. Hosted runtime writes an
identifier-only outbox request in the same transaction, then a retry-safe worker
loads the exact context, decision and capability reviews before recording the
critique. JIOC Managers see the result as oversight evidence only.

---

## 4. Bounded agents

```mermaid
flowchart LR
    IN["Intake controller<br/>deterministic safety, extraction,<br/>contradictions + completeness"]
    IP["Intake Planner<br/>bounded missing-field preference"]
    RFI["RFI search<br/>authorised baseline retrieval"]
    SP["Search Planner<br/>additive wording only"]
    AW["Active-work discovery<br/>authorised open work"]
    CAP["RFA + CM capability agents<br/>deterministic evidence"]
    JIOC["JIOC Agent<br/>active policy route"]
    CRIT["Routing Critic<br/>shadow-only challenge"]
    JM{{"JIOC Manager<br/>on-loop oversight<br/>in-loop exceptions"}}

    IP -. advice .-> IN --> RFI
    SP -. supplemental query .-> RFI --> AW --> CAP --> JIOC
    JIOC -. committed facts .-> CRIT -. oversight evidence .-> JM
    JM -. hold or review .-> JIOC

    classDef det fill:#4f46e5,stroke:#3730a3,color:#fff
    classDef model fill:#9333ea,stroke:#6b21a8,color:#fff
    classDef human fill:#dc2626,stroke:#991b1b,color:#fff
    class IN,RFI,AW,CAP,JIOC det
    class IP,SP,CRIT model
    class JM human
```

The Intake Planner does not discover contradictions or ambiguity through model
judgement. Deterministic checks detect reversed or invalid dates, broad
geography, vague dates and compound questions. Those findings override model
output. When the baseline action is to ask for missing information, admitted
model advice may select one field from the controller-supplied missing-field
list. The controller renders all user-facing copy and alone decides readiness.

The Search Planner receives bounded intake fields, never the corpus, results or
authorisation context. Its validated expansions, entities, date-text hints and
alternative terminology may create a separate supplemental retrieval leg. The
original access-filtered baseline query always runs first, and baseline offers
cannot be removed or displaced by planner advice. Planner failure falls back to
the baseline search.

The Routing Critic receives structured facts about the committed route,
disposition, state, search assurance, capability reviews and capacity. It may
return only allowlisted verdict, challenge, missing-evidence, fact-reference and
review-question codes. It cannot propose a route, state, action, disposition or
tool call. Provider advice is merged with deterministic checks so it cannot
erase a locally detected problem.

---

## 5. Hybrid Store and RFI search

Store browse and RFI search share the same retrieval boundary. Access policy
filters by ACG, clearance and product status before ranking. Lexical and semantic
legs run over that scoped set, Reciprocal Rank Fusion combines them, and
deterministic metadata and label signals break ties. Offers must pass the
calibrated threshold and are limited to five.

The embedding provider is selectable: deterministic `mock`, offline `local` or
explicit `gemini_api`. When embeddings are unavailable, the baseline search
degrades to lexical retrieval and records the degraded mode. Search assurance
prevents an incomplete retrieval from being treated as a definitive no-match.

See [AI Agents](AI_AGENTS.md) for each agent's inputs, output schema, fallback,
owner, versioning and egress boundary.
