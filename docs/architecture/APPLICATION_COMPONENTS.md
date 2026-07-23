# Application Component Views

Status: **implemented** unless marked otherwise. Verified against `e44b66b6` on
23 July 2026.

This page drills from browser and service containers into frontend and backend
components, then follows one authenticated mutation through the final authority
boundary. See [Security and trust](SECURITY_AND_TRUST.md) for policy detail and
[Data, search and AI](DATA_SEARCH_AND_AI.md) for persistence internals.

## 1. Runtime containers and external calls

The browser fetches the SPA from the web origin and calls the configured API
origin directly. nginx is not an API reverse proxy.

```mermaid
flowchart LR
    accTitle: Istari runtime container view
    accDescr: The browser loads a React SPA from the web server, calls FastAPI directly, and FastAPI uses PostgreSQL, local object storage and optional external providers.

    U["User browser"]
    WEB["React SPA<br/>Vite development server or nginx"]
    API["FastAPI<br/>Uvicorn, one process and one worker"]
    PG[("PostgreSQL + pgvector")]
    OBJ[["Local object root<br/>uploads, products and previews"]]
    LLM["OPTIONAL<br/>LLM or LiteLLM provider"]
    EMB["OPTIONAL<br/>Gemini embedding provider"]
    RT["OPTIONAL<br/>OpenAI Realtime"]
    SMTP["OPTIONAL<br/>SMTP relay"]

    U -->|"GET HTML, JS and CSS"| WEB
    U -->|"credentialed CORS<br/>cookie + CSRF on mutations"| API
    API -->|"SQL and transactions"| PG
    API -->|"atomic byte writes and streams"| OBJ
    API -.->|"explicit provider selection"| LLM
    API -.->|"explicit provider selection"| EMB
    API -.->|"SDP broker only"| RT
    U -.->|"negotiated WebRTC"| RT
    API -.->|"smtp only when selected"| SMTP
```

The local default stays offline for text, embeddings and email. Realtime voice
is unavailable until configured.

## 2. Frontend component view

```mermaid
flowchart TB
    accTitle: React frontend component architecture
    accDescr: Router and session context establish the shell, route policy controls navigation, feature pages use TanStack Query and typed API clients, and the server remains authoritative.

    ENTRY["main.tsx<br/>React root"]
    APP["App.tsx"]
    PROVIDERS["AppProviders<br/>QueryClientProvider"]
    ROUTER["router.tsx<br/>lazy route tree + recovery"]
    AUTH["AuthProvider<br/>session, login, logout, cache clearing"]
    SHELL["AuthenticatedShell<br/>navigation, command bar, notifications"]
    RP["route-policy.ts<br/>route permission metadata"]
    NAV["route-access.ts<br/>visible navigation"]

    subgraph features["Role feature boundaries"]
        REQ["Requests and intake"]
        ACCESS["Access Groups"]
        STORE["Intelligence Store"]
        ROUTING["JIOC, RFA and CM queues"]
        ANALYST["Analyst workbench"]
        QC["QC queue"]
        ADMIN["Admin, analytics and audit"]
    end

    QUERY["TanStack Query<br/>server-state cache and invalidation"]
    MUT["Shared mutation error handling"]
    CLIENT["lib/api-client<br/>typed JSON/multipart fetch"]
    API["Configured FastAPI origin"]

    ENTRY --> APP --> PROVIDERS --> AUTH --> ROUTER --> SHELL
    RP --> ROUTER
    RP --> NAV --> SHELL
    SHELL --> features
    features --> QUERY --> CLIENT --> API
    features --> MUT --> CLIENT
```

Frontend guards prevent confusing navigation, not unauthorised access. Every
direct link and mutation is re-evaluated by the API.

## 3. Backend component view

```mermaid
flowchart TB
    accTitle: FastAPI backend component architecture
    accDescr: Thin route groups use shared dependencies and domain services, which call repository, integration and storage ports composed into PostgreSQL and local adapters.

    MAIN["main.py<br/>lifespan, middleware, 24 route groups"]
    DEP["api/dependencies.py<br/>session, CSRF and permission predicates"]

    subgraph routes["Thin API route groups"]
        IDR["auth, admin, users, access"]
        WR["tickets, RFI, similar, routing"]
        PR["analyst, QC, Store, files, previews"]
        OR["teams, profiles, feedback, analytics,<br/>notifications, voice, health"]
    end

    subgraph services["Business and authority services"]
        IDS["identity and ACG services"]
        WFS["ticket, routing and outcome services"]
        PROD["assignment, analyst, QC and Store services"]
        SEARCH["browse, grounded search and indexing"]
        OPS["audit, notifications, outbox and analytics"]
    end

    DOMAIN["domain<br/>enums, dataclasses, policy and state machine"]
    PORTS["application ports<br/>repositories, storage, advisory, outbox"]
    PERSIST["persistence adapters<br/>transactions, relational stores, compatibility state"]
    INTEG["integration adapters<br/>LLM HTTP, Realtime and SMTP"]
    PG[("PostgreSQL")]
    FS[["Local object storage"]]

    MAIN --> routes
    routes --> DEP
    routes --> services
    services --> DOMAIN
    services --> PORTS
    PORTS --> PERSIST --> PG
    PORTS --> INTEG
    PROD --> FS
    SEARCH --> PG
```

Composition is explicit in `composition.py` and focused composition modules.
Services receive repositories and provider ports rather than importing
framework globals.

## 4. Request execution and commit boundary

Read-only requests skip CSRF. Mutations pass the applicable predicates, then the
service repeats object/action checks at the final boundary. This sequence shows
a representative relational workflow mutation; the referenced authority,
projection and intent sets depend on the command.

```mermaid
sequenceDiagram
    accTitle: Relational workflow mutation and authority-fenced commit
    accDescr: A browser mutation passes session, CSRF, action and object checks before a service locks applicable current authority and atomically commits the versioned workflow plus applicable audit, projection and outbox records.
    autonumber

    actor U as Browser user
    participant R as FastAPI route
    participant D as Shared dependencies
    participant S as Domain service
    participant T as Workflow transaction
    participant DB as PostgreSQL

    U->>R: Mutation with cookie and X-CSRF-Token
    R->>D: Resolve session and active account
    D->>D: Compare CSRF token and required permission
    D-->>R: Authenticated actor
    R->>S: Validated command
    S->>S: Object, state and separation-of-duties policy
    S->>T: Expected aggregate, authority snapshot, audit and intents
    T->>DB: BEGIN and lock referenced authority namespaces
    T->>DB: Re-evaluate user, session, ACG, product and ticket as applicable
    alt authority changed
        T->>DB: ROLLBACK
        T-->>S: 403, 404 or bounded conflict
    else current authority
        T->>DB: Compare ticket version and canonical hash
        T->>DB: Write aggregate plus applicable projections, audit and outbox
        T->>DB: COMMIT
        T-->>S: Committed version
        S-->>R: Response model
        R-->>U: Bounded success response
    end
```

Compatibility-state services use guarded single-process saves and compensation
rather than the relational workflow transaction. This is one reason the current
deployment remains one API process.

## 5. Background and post-commit effects

```mermaid
flowchart LR
    accTitle: Background and post-commit effect composition
    accDescr: Relational workflow commits create durable intents; hosted composition polls and dispatches them, while local routing criticism is inline and a release-notification limitation remains.

    TX["Committed workflow transaction"]
    OB[("coeus_outbox<br/>deterministic event ID")]
    POLL["Hosted in-process poller<br/>fenced claim and retry"]
    DISC["Active-work discovery handler"]
    CRIT["Routing critic handler<br/>oversight only"]
    NOTIFY["Release notification handler<br/>in-app + retained email or SMTP"]
    DEAD["Dead letter<br/>audited operator replay"]
    INLINE["Local/test routing critic<br/>best effort after route"]
    GAP["LIMITATION<br/>local relational release intent can remain pending:<br/>dispatcher is installed only in hosted composition"]

    TX --> OB --> POLL
    POLL --> DISC
    POLL --> CRIT
    POLL --> NOTIFY
    POLL -->|"attempt ceiling"| DEAD
    DEAD -->|"same event ID"| POLL
    TX -.->|"local/test routing path"| INLINE
    OB -.->|"local release path"| GAP
```

The dispatcher is an in-process task, not a separately deployed worker. Handler
idempotency is mandatory because an external effect can complete before the
delivery row is settled.

## Sources and companion records

| Concern                 | Authority                                                                                                                |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Application composition | `apps/api/src/coeus/main.py`, `composition.py`, `identity_composition.py`                                                |
| Frontend routing        | `apps/web/src/app/router.tsx`, `app/route-policy.ts`, `lib/permissions/route-access.ts`                                  |
| Workflow transaction    | `apps/api/src/coeus/persistence/workflow_transaction.py`, `workflow_authority.py`                                        |
| Background dispatch     | `apps/api/src/coeus/services/outbox_dispatcher.py`, `release_notification_handler.py`                                    |
| Developer guidance      | [Backend boundaries](../development/backend-boundaries.md), [Frontend boundaries](../development/frontend-boundaries.md) |
| Operational guidance    | [Workflow and outbox operations](../security/workflow-outbox-operations.md)                                              |
