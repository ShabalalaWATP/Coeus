# Istari Architecture: Workflow

How a request moves through Istari from a user's point of view, who does what,
and where the AI agents assist without ever making the decision. This is one of
three architecture guides; see [Architecture](ARCHITECTURE.md) for the system
structure and [Architecture: Deployment](ARCHITECTURE_DEPLOYMENT.md) for runtime
and cloud. Every diagram reflects the shipped code.

---

## 1. The request journey (user perspective)

From a customer's point of view, a request is a conversation that becomes a
tracked item moving through clear stages. This is the ticket state machine; the
only transitions that exist are the ones drawn here, and a person triggers each
state change.

```mermaid
stateDiagram-v2
    [*] --> DRAFT_INTAKE: start a chat
    DRAFT_INTAKE --> RFI_SEARCHING: submit (7 of 7 captured)
    RFI_SEARCHING --> RFI_MATCH_OFFERED: existing products found
    RFI_SEARCHING --> RFI_NO_MATCH: nothing suitable found

    RFI_MATCH_OFFERED --> CLOSED_EXISTING_PRODUCT_ACCEPTED: accept an offer
    RFI_MATCH_OFFERED --> ROUTE_ASSESSMENT: reject all offers

    RFI_NO_MATCH --> ROUTE_ASSESSMENT: task as new request (yes)
    RFI_NO_MATCH --> CANCELLED: decline (no)

    ROUTE_ASSESSMENT --> RFA_MANAGER_REVIEW: assessment route
    ROUTE_ASSESSMENT --> CM_MANAGER_REVIEW: collection route
    RFA_MANAGER_REVIEW --> ANALYST_ASSIGNMENT: approve
    CM_MANAGER_REVIEW --> ANALYST_ASSIGNMENT: approve
    RFA_MANAGER_REVIEW --> INFO_REQUIRED: request clarification
    CM_MANAGER_REVIEW --> INFO_REQUIRED: request clarification

    ANALYST_ASSIGNMENT --> ANALYST_IN_PROGRESS: analyst assigned
    ANALYST_IN_PROGRESS --> QC_REVIEW: submit to QC
    QC_REVIEW --> MANAGER_RELEASE: QC approves
    QC_REVIEW --> REWORK_REQUIRED: QC rejects
    REWORK_REQUIRED --> ANALYST_IN_PROGRESS: rework

    MANAGER_RELEASE --> DISSEMINATION_READY: manager releases
    DISSEMINATION_READY --> CLOSED_DELIVERED: customer confirms receipt
    CLOSED_DELIVERED --> [*]

    CLOSED_EXISTING_PRODUCT_ACCEPTED --> [*]
    CANCELLED --> [*]
```

Two recently added stops are worth calling out: **RFI_NO_MATCH** gives the
customer an explicit yes/no decision ("no existing product matches, task this as
a new request?") instead of silently raising new work, and **CLOSED_DELIVERED**
lets the customer confirm receipt so a delivered request can actually close.

---

## 2. End-to-end flow (who does what)

The same journey as a sequence, showing where each agent assists and where a
human decides. Every agent output is followed by a human action.

```mermaid
sequenceDiagram
    autonumber
    actor C as Customer
    participant CB as Chatbot agent
    participant RFI as RFI search agent
    actor M as RFA / CM manager
    participant CAP as Capability + orchestrator agents
    actor A as Analyst
    actor Q as QC manager

    C->>CB: describe the need in chat
    CB-->>C: extract 7 fields, flag gaps, refuse injections
    C->>RFI: submit the requirement
    RFI-->>C: ranked existing-product offers (hybrid search)
    alt an offer fits
        C->>C: accept -> request closed against existing product
    else nothing fits
        C->>C: confirm "task as new request"
        C->>M: request enters the manager queue
        CAP-->>M: RFA/CM feasibility + recommended route
        M->>A: approve route, assign analyst (human decision)
        A->>Q: produce draft, submit to QC
        Q->>M: approve with ACGs (or reject for rework)
        M->>C: release product, notify customer
        C->>C: confirm receipt -> request closed, delivered
    end
```

---

## 3. AI agents

A small set of focused agents sit behind the workflow. They are deterministic
mocks by default, never execute user instructions, and treat every input as
synthetic. Each agent hands a recommendation to a human. See
[AI Agents](AI_AGENTS.md) for exactly what each reads and returns.

```mermaid
flowchart LR
    subgraph stage1["Describe"]
        CB["Customer chatbot<br/>extract 7 fields<br/>completeness + safety"]
    end
    subgraph stage2["Search"]
        RFI["RFI search<br/>hybrid ranking<br/>existing-product offers"]
        SIM["Similar-request check<br/>overlapping open work"]
    end
    subgraph stage3["Route"]
        RFACAP["RFA capability<br/>assessment feasibility"]
        CMCAP["CM capability<br/>collection feasibility"]
        ORCH["Orchestrator<br/>recommended route + reason"]
    end

    CB --> RFI --> ORCH
    RFI -. informs .-> SIM
    RFACAP --> ORCH
    CMCAP --> ORCH

    HUMAN{{"Human decides<br/>at every stage"}}
    CB --> HUMAN
    RFI --> HUMAN
    ORCH --> HUMAN

    classDef ai fill:#9333ea,stroke:#6b21a8,color:#fff,stroke-width:1px
    classDef human fill:#dc2626,stroke:#991b1b,color:#fff,stroke-width:2px
    class CB,RFI,SIM,RFACAP,CMCAP,ORCH ai
    class HUMAN human
```

### Hybrid RFI search internals

The RFI search agent answers "does an existing product already satisfy this?"
before new work is raised. The candidate set is filtered by the requester's ACG,
clearance and product status **first**, so the agent can never rank a product the
requester has no need-to-know for. Two retrieval legs then run over that scoped
set and are fused.

```mermaid
flowchart TB
    Q["Requester intake<br/>title, question, region, format, criteria"]
    SCOPE["Access pre-filter<br/>ACG + clearance + status"]
    subgraph legs["Two retrieval legs over the scoped set"]
        LEX["Lexical leg<br/>Postgres tsvector<br/>websearch_to_tsquery + ts_rank_cd"]
        VEC["Semantic leg<br/>pgvector cosine ANN<br/>384-dim embedding"]
    end
    RRF["Reciprocal Rank Fusion<br/>k = 60"]
    BOOST["Metadata + label boosts<br/>region, format, semantic labels"]
    OFFERS["Ranked offers<br/>threshold 0.34, top 5<br/>with human-readable reasons"]

    Q --> SCOPE --> LEX --> RRF
    SCOPE --> VEC --> RRF
    RRF --> BOOST --> OFFERS

    classDef ai fill:#9333ea,stroke:#6b21a8,color:#fff,stroke-width:1px
    classDef sec fill:#dc2626,stroke:#991b1b,color:#fff,stroke-width:1px
    classDef data fill:#b45309,stroke:#7c2d12,color:#fff,stroke-width:1px
    class Q,RRF,BOOST,OFFERS ai
    class SCOPE sec
    class LEX,VEC data
```

The embedding provider is selectable (`mock` by default, `local` for an offline
sentence model, `gemini_api` when explicitly enabled). If the provider is
unavailable, search degrades to the lexical leg alone rather than failing, and
the offer reasons record `retrieval:lexical-only`. The same hybrid scorer backs
the similar-request check that flags overlapping in-progress work to managers.
