# Data, Search and AI Views

Status: **implemented** unless marked otherwise. Verified against `e44b66b6` on
23 July 2026.

This page distinguishes authoritative records, compatibility projections,
derived indexes and optional model assistance. These distinctions matter during
transactions, degraded search and recovery.

## 1. Data authority and ownership

```mermaid
flowchart TB
    accTitle: Istari data authority and ownership
    accDescr: Application domains map to authoritative relational records, compatibility JSON state, derived indexes, local object bytes and an external configuration key.

    subgraph domains["Application-owned domains"]
        ID["Identity and authority"]
        WF["Versioned workflow"]
        STORE["Intelligence Store"]
        AUD["Audit evidence"]
        CFG["Configuration and notifications"]
        SEARCH["Derived search"]
        CAP["Ephemeral resource admission"]
    end

    subgraph pg["PostgreSQL"]
        STATE[("coeus_state<br/>bounded JSONB namespaces")]
        TICKETS[("coeus_ticket_aggregates<br/>canonical hash + version")]
        OUTBOX[("coeus_outbox<br/>durable effect intents")]
        EVENTS[("coeus_audit_events<br/>application append-only")]
        AUDIENCE[("coeus_draft_audiences<br/>visibility projection")]
        STOREDB[("Relational Store tables")]
        BROWSE[("Store browse projection<br/>vector(384)")]
        PROFILE[("Search index profiles")]
        GROUND[("Grounded generation tables<br/>vector(1536)")]
        LEASES[("coeus_resource_leases")]
    end

    OBJECTS[["Local object root<br/>workflow and Store bytes"]]
    KEY[["Configuration encryption key<br/>outside database and recovery bundle;<br/>backed up separately"]]
    LOCAL["Local/test process-local<br/>resource admission"]

    ID --> STATE
    CFG --> STATE
    CFG -.->|"encrypted values"| KEY
    WF --> TICKETS
    WF --> OUTBOX
    WF --> AUDIENCE
    WF -.->|"counter and compatibility data"| STATE
    STORE --> STOREDB
    STORE --> OBJECTS
    STORE -.->|"compatibility snapshot"| STATE
    AUD --> EVENTS
    STOREDB --> BROWSE
    SEARCH --> PROFILE --> GROUND
    TICKETS --> GROUND
    STOREDB --> GROUND
    OBJECTS --> GROUND
    CAP --> LOCAL
    CAP -.->|"hosted composition only"| LEASES
```

Relational ticket, Store and audit records are authoritative in the default
PostgreSQL composition. `coeus_state` still contains bounded identity,
configuration, notification and compatibility namespaces. Grounded indexes and
resource leases are not business records. Local/test admission is process-local;
the relational lease adapter is selected only in hosted composition.

## 2. Logical relationship view

This is a domain-level ERD, not a complete physical schema.

```mermaid
erDiagram
    accTitle: Core workflow, Store and search relationships
    accDescr: Tickets relate to drafts, audit and outbox intents; Store products relate to assets and access groups; generation profiles own derived chunks and embeddings.

    USER ||--o{ SESSION : owns
    USER }o--o{ ROLE : holds
    USER }o--o{ ACCESS_GROUP : member_of
    USER ||--o{ TICKET : requests
    TICKET ||--o{ DRAFT_AUDIENCE : projects
    TICKET o|--o{ AUDIT_EVENT : "optional ticket metadata subset"
    TICKET ||--o{ OUTBOX_INTENT : emits
    TICKET }o--o{ STORE_PRODUCT : references
    STORE_PRODUCT ||--o{ STORE_ASSET : contains
    STORE_PRODUCT }o--o{ ACCESS_GROUP : scoped_by
    STORE_PRODUCT }o--o{ STORE_LABEL : labelled
    INDEX_PROFILE ||--o{ PRODUCT_CHUNK : owns
    INDEX_PROFILE ||--o{ TICKET_EMBEDDING : owns
    STORE_PRODUCT ||--o{ PRODUCT_CHUNK : derives
    TICKET ||--o{ TICKET_EMBEDDING : derives

    USER {
        uuid id PK
        string status
        string clearance
    }
    TICKET {
        string id PK
        integer version
        string canonical_hash
        json aggregate
    }
    STORE_PRODUCT {
        string id PK
        string status
        string classification
    }
    STORE_ASSET {
        string id PK
        string object_key
        string sha256
    }
    INDEX_PROFILE {
        string id PK
        string provider
        string model
        integer generation
        boolean active
    }
```

## 3. Object-byte custody

```mermaid
sequenceDiagram
    accTitle: Product object custody and provenance
    accDescr: An upload is bounded and inspected before an atomic object write, draft metadata is versioned, QC copies exact bytes into a new Store identity, and downloads recheck current policy.
    autonumber

    actor A as Analyst
    actor Q as QC manager
    actor C as Authorised consumer
    participant API as FastAPI
    participant STAGE as Bounded staging
    participant INSPECT as Content inspection
    participant OBJ as Local object root
    participant T as Ticket authority
    participant S as Store authority

    A->>API: Multipart metadata and asset
    API->>STAGE: Stream with byte and concurrency limits
    STAGE->>INSPECT: Digest, type, archive and semantic checks
    INSPECT-->>API: Detected MIME, SHA-256 and bounded text
    API->>OBJ: Atomic write under workflow/submissions
    API->>T: Compare-and-set immutable draft manifest
    alt ticket commit fails
        API->>OBJ: Delete newly written object
    else draft accepted
        API-->>A: New draft version
    end
    Q->>OBJ: Read and verify exact draft bytes
    Q->>OBJ: Copy to new store/qc object identity
    Q->>S: Create DRAFT product and asset digest
    Q->>T: Authority-fenced publish transaction
    alt release fails
        Q->>S: Compensate metadata
        Q->>OBJ: Delete copied object
    else release succeeds
        T-->>C: Product becomes policy-visible
    end
    C->>API: Request then redeem short-lived asset grant
    API->>API: Re-evaluate current product policy
    API->>OBJ: Stream verified object
    API-->>C: no-store response
```

The direct Store upload path uses the same bounded staging and inspection
controls. Database and filesystem changes use compensation; they are not
presented as one cross-store atomic transaction.

## 4. Two-index retrieval and assurance

```mermaid
flowchart LR
    accTitle: Access-filtered two-index retrieval pipeline
    accDescr: Authoritative baseline and optional planner queries search a 384-dimensional Store projection and 1536-dimensional grounded generation, then deterministic fusion records coverage and assurance.

    REQ["Authorised request context"]
    POLICY["Clearance, ACG, status,<br/>draft and collaboration policy"]
    BASE["DETERMINISTIC<br/>authoritative baseline query"]
    PLAN["OPTIONAL MODEL<br/>additive query plan"]

    subgraph compat["Compatibility retrieval"]
        STORE[("Store relational projection<br/>text + vector(384)")]
        BROWSE["Product offers and browse"]
    end

    subgraph grounded["Generation-aware retrieval"]
        PROFILE["Active provider/model profile"]
        CHUNKS[("Product chunks<br/>vector(1536)")]
        WORK[("Visible open tickets<br/>vector(1536)")]
        EVIDENCE["Grounded evidence"]
    end

    FUSE["DETERMINISTIC<br/>deduplicate, rank and bound"]
    ASSURE["Persist retrieval mode,<br/>coverage and assurance"]
    RESULT["Authorised offers or<br/>retry/incomplete state"]

    REQ --> POLICY
    POLICY --> BASE
    POLICY -.-> PLAN
    BASE --> STORE --> BROWSE --> FUSE
    BASE --> PROFILE
    PLAN -.-> PROFILE
    PROFILE --> CHUNKS --> EVIDENCE --> FUSE
    PROFILE --> WORK --> EVIDENCE
    FUSE --> ASSURE --> RESULT
```

The two vector dimensions serve different schemas and cannot be interchanged.
The optional planner may add retrieval legs but cannot remove the deterministic
baseline. Provider failure preserves a bounded, explainable fallback and is
recorded in the assurance result.

## 5. Shadow index generation

```mermaid
stateDiagram-v2
    accTitle: Grounded search index generation lifecycle
    accDescr: Each attempt creates a new profile that fails terminally or becomes the active ready profile; an activation-operation failure restores the previous profile internally, but no operator rollback or retention path exists.

    state "Candidate failed;<br/>previous ready profile reactivated" as CompensatedFailure

    [*] --> Indexing: create new inactive profile UUID
    Indexing --> Indexing: batch products and open tickets
    Indexing --> Failed: provider, validation or coverage failure
    Indexing --> ActiveReady: complete and activate one winner
    ActiveReady --> CompensatedFailure: post-activation configuration persistence fails
    ActiveReady --> InactiveReady: a later distinct profile activates
    Failed --> [*]: this profile remains failed
    CompensatedFailure --> [*]: candidate remains failed
    InactiveReady --> Limitation: no authorised rollback or cleanup path
```

Logical backups exclude these derived generation tables. After restore,
operators must rebuild and verify a generation before relying on complete
grounded-search assurance. Previous ready generations remain in the database,
but no operator rollback command, generation retirement state or cleanup policy
is implemented. `rollback_activation` is narrower: it is internal compensation
within one failed activation operation and reactivates the previous profile.

## 6. Bounded AI authority

```mermaid
flowchart TB
    accTitle: Deterministic and model authority boundaries
    accDescr: Deterministic controllers own validation, transitions and commits; optional model adapters can structure or criticise bounded inputs but cannot authorise or mutate state directly.

    HUMAN["HUMAN<br/>request, consent, review and approval"]
    API["Validated application command"]
    CTRL["DETERMINISTIC<br/>policy, state machine and transaction"]
    PORT["Provider port<br/>timeouts, circuit and response bounds"]
    MODEL["OPTIONAL MODEL<br/>intake, query planning or criticism"]
    CHECK["DETERMINISTIC<br/>schema, evidence and eligibility checks"]
    COMMIT["Authority-fenced commit"]
    AUDIT["Audit and assurance evidence"]
    FALLBACK["Safe local fallback or explicit abstention"]

    HUMAN --> API --> CTRL
    CTRL -.->|"bounded prompt, selected provider"| PORT
    PORT -.-> MODEL
    MODEL -.-> CHECK
    PORT -->|"unavailable or invalid"| FALLBACK --> CTRL
    CHECK --> CTRL
    CTRL --> COMMIT --> AUDIT
```

The Routing Critic runs after a route is committed and is oversight-only.
Realtime voice is a separate browser-to-provider trust boundary documented in
[Security and trust](SECURITY_AND_TRUST.md#6-external-provider-and-realtime-boundaries).

## Sources and companion records

| Concern                 | Authority                                                                                                                                            |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Relational schemas      | `apps/api/src/coeus/persistence/relational_schema.py`, `search_index_schema.py`                                                                      |
| Workflow transactions   | `apps/api/src/coeus/persistence/workflow_transaction.py`, `workflow_authority.py`                                                                    |
| Object lifecycle        | `product_submissions.py`, `qc_ingestion.py`, `qc_release.py`, `object_storage.py`                                                                    |
| Retrieval and assurance | `grounded_search.py`, `rfi_search_retrieval.py`, `rfi_search.py`                                                                                     |
| Index generation        | `search_indexing.py`, `search_index_repository.py`                                                                                                   |
| Feature contracts       | [Hybrid RFI search](../specs/hybrid-rfi-search.md), [Search retrieval and duplicate assurance](../specs/search-retrieval-and-duplicate-assurance.md) |
| Operations              | [Coordinated backup and restore](../runbooks/coordinated-backup-restore.md), including separate key preservation                                     |
