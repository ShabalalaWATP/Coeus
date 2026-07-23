# Security and Trust Views

Status: **implemented** unless marked otherwise. Verified against `e44b66b6` on
23 July 2026.

These views show where identity, policy and human authority are re-evaluated.
They are an orientation aid, not a replacement for the linked threat models.

## 1. Trust zones and data movement

```mermaid
flowchart LR
    accTitle: Istari trust zones and principal data flows
    accDescr: An untrusted browser crosses the API enforcement boundary; the API controls database and object access and makes only explicitly configured outbound provider calls.

    subgraph client["Untrusted client zone"]
        B["Browser SPA<br/>untrusted input and display"]
    end

    subgraph app["Istari application trust zone"]
        API["FastAPI<br/>validation, authentication and policy"]
        SERVICE["Domain services<br/>state, object and action authority"]
        ADAPTER["Controlled adapters<br/>timeouts, bounds and sanitisation"]
    end

    subgraph data["Application data zone"]
        PG[("PostgreSQL<br/>authority and audit evidence")]
        OBJ[["Local object root<br/>controlled product bytes"]]
        KEY[["Configuration key<br/>separate operator secret"]]
    end

    subgraph external["Optional external provider zones"]
        TEXT["LLM or LiteLLM"]
        EMB["Gemini embeddings"]
        RT["OpenAI Realtime"]
        MAIL["SMTP relay"]
    end

    B -->|"loopback HTTP locally;<br/>TLS + secure cookie when hosted;<br/>CSRF on mutation"| API
    API --> SERVICE --> PG
    SERVICE --> OBJ
    SERVICE --> ADAPTER
    KEY -.->|"decrypt selected credential"| ADAPTER
    ADAPTER -.->|"bounded prompt or text"| TEXT
    ADAPTER -.->|"bounded text"| EMB
    ADAPTER -.->|"SDP setup"| RT
    B -.->|"explicit microphone start<br/>direct WebRTC"| RT
    ADAPTER -.->|"bounded retained message"| MAIL
```

Ordinary runtime egress is off by default and begins when an operator selects an
environment provider or an administrator enables an application-managed
provider. Administrator-requested connectivity tests and model discovery can
contact a configured provider before activation. Text and voice connection
tests are not separately audited; a successful model refresh is. The database
administrator and host operator remain inside the trusted computing boundary.
Audit rows are application-append-only, not database-trigger immutable or WORM
storage.

## 2. Request authentication and need-to-know

```mermaid
flowchart TB
    accTitle: Request authentication and object-policy decision
    accDescr: Session and active-account checks precede mutation-only CSRF, action permission and object policy; hidden objects return not-found and sensitive commits recheck authority.

    REQ["HTTP request"]
    SESSION{"Valid active session<br/>and credential version?"}
    MUT{"State-changing?"}
    CSRF{"CSRF token matches?"}
    PERM{"Required action<br/>permission?"}
    OBJECT{"Object policy passes?<br/>owner, team, clearance, ACG,<br/>status, audience and role"}
    SERVICE["Service command"]
    FINAL{"Sensitive commit or<br/>asset redemption?"}
    FENCE{"Re-read mutable authority,<br/>version and canonical hash"}
    OK["Bounded response"]
    UNAUTH["401 generic authentication response"]
    FORBID["403 bounded action denial"]
    REVOKED["403 authority revoked"]
    HIDDEN["404 hidden-object response"]
    CONFLICT["409 stale version or hash"]

    REQ --> SESSION
    SESSION -->|"no"| UNAUTH
    SESSION -->|"yes"| MUT
    MUT -->|"yes"| CSRF
    CSRF -->|"no"| FORBID
    CSRF -->|"yes"| PERM
    MUT -->|"no"| PERM
    PERM -->|"no"| FORBID
    PERM -->|"yes"| OBJECT
    OBJECT -->|"known action forbidden"| FORBID
    OBJECT -->|"resource existence concealed"| HIDDEN
    OBJECT -->|"yes"| SERVICE --> FINAL
    FINAL -->|"no"| OK
    FINAL -->|"yes"| FENCE
    FENCE -->|"actor or object authority revoked"| REVOKED
    FENCE -->|"ticket version or hash changed"| CONFLICT
    FENCE -->|"current"| OK
```

Frontend route policy improves navigation but is never an authorisation
boundary. Ordinary denials are not described as audit evidence unless the
governing service explicitly records them.

## 3. Session and credential lifecycle

```mermaid
stateDiagram-v2
    accTitle: Browser session and credential lifecycle
    accDescr: Generic login attempts are admitted through bounded password work, active sessions rotate or expire, and credential or account changes revoke stale sessions.

    [*] --> SignedOut
    SignedOut --> LoginAdmitted: bounded rate and Argon2 capacity
    LoginAdmitted --> SignedOut: generic invalid response
    LoginAdmitted --> Active: active account and valid password
    LoginAdmitted --> TemporarilyBlocked: attempt or capacity limit
    TemporarilyBlocked --> SignedOut: bounded retry window
    Active --> Active: authenticated read or CSRF-valid mutation
    Active --> SignedOut: logout
    Active --> Expired: idle or absolute expiry
    Active --> Revoked: disable, reset or credential-version change
    Active --> Replaced: successful password change
    Replaced --> Active: fresh session issued
    Expired --> SignedOut
    Revoked --> SignedOut
```

Session IDs stay in HTTP-only SameSite cookies. CSRF material stays in React
memory, not local storage. Hosted startup requires secure cookies. Session
issue is bounded globally and per user.

## 4. ACG application and delegated review

```mermaid
sequenceDiagram
    accTitle: Access-control-group application governance
    accDescr: A requester applies to an active group, a currently delegated reviewer makes the first valid non-self decision, and approval adds membership only when workflow and audit persistence succeed.
    autonumber

    actor U as Requester
    actor D as Delegated ACG administrator
    participant API as FastAPI
    participant S as ACG application service
    participant R as Authority repository
    participant A as Audit store

    U->>API: Apply with bounded justification and CSRF
    API->>S: Authenticated application command
    S->>R: Confirm active group and no active membership
    S->>R: Create PENDING application
    S->>A: Record identifier-only submission evidence
    S-->>U: Pending status
    D->>API: Review delegated queue
    API->>S: Approve or reject with bounded reason
    S->>R: Recheck live roster, actor, group and pending state
    alt self-decision, stale or no longer delegated
        S-->>D: Bounded denial or conflict
    else rejection
        S->>R: Set rejected
        S->>A: Record decision without reason text
    else approval
        S->>R: Set approved and add membership
        S->>A: Record decision and membership identifiers
        alt persistence or audit fails
            S->>R: Restore application and membership state
            S-->>D: Fail closed
        end
    end
```

Delegated administration is a responsibility, not a role or membership.
Review authority never grants product access. This path currently uses a
single-writer authority boundary with compensation, not a multi-replica
transaction.

## 5. Controlled asset grant and redemption

```mermaid
sequenceDiagram
    accTitle: Normal and break-glass product asset access
    accDescr: Normal access requires live object policy; exceptional support access requires restricted-read authority and a reason, produces audit evidence, and both paths use short-lived header tokens rechecked at redemption.
    autonumber

    actor U as User
    participant API as FastAPI
    participant P as Product policy
    participant G as Asset-grant service
    participant A as Audit store
    participant O as Object storage

    U->>API: Request asset access
    alt normal access
        API->>P: Require PRODUCT_DOWNLOAD
        P->>P: Check clearance, ACG, status and draft audience
        P-->>API: Visible product and asset
    else break-glass requested
        API->>P: Require PRODUCT_READ_RESTRICTED and bounded reason
        P-->>A: Record exceptional access reason and target
        P-->>API: Explicit break-glass authority
    else denied
        API-->>U: 404 hidden object
    end
    API->>G: Issue short-lived principal-bound HMAC grant
    G-->>U: X-Asset-Token value
    U->>API: Redeem token in request header
    API->>G: Verify signature, expiry, principal and asset
    G->>P: Re-evaluate current mutable authority
    alt authority revoked or token invalid
        API-->>U: Bounded denial
    else authorised
        API->>O: Stream current object in bounded chunks
        API-->>U: Cache-Control no-store
    end
```

Break-glass deliberately bypasses ordinary product clearance, ACG, status and
draft checks only after restricted-read support authority and a reason are
validated. It is an exceptional, audited path, not an administrator shortcut.

## 6. External-provider and Realtime boundaries

```mermaid
sequenceDiagram
    accTitle: Optional provider configuration and Realtime voice boundary
    accDescr: Configuration, optional connectivity testing and enablement are separate; ordinary model calls stay server-side, while a voice user explicitly starts an API-brokered session before media flows directly to OpenAI.
    autonumber

    actor AD as Administrator
    actor U as Voice user
    participant API as FastAPI
    participant CFG as Encrypted configuration
    participant MODEL as Selected text or embedding provider
    participant RT as OpenAI Realtime

    AD->>API: Save credential and selected settings
    API->>CFG: Encrypt application-managed credential
    opt administrator requests a separate connectivity test
        AD->>API: Test selected provider
        API->>MODEL: Bounded server-side test
        MODEL-->>API: Sanitised result
        API-->>AD: Test result
    end
    AD->>API: Enable or activate configured provider
    API->>CFG: Set enabled or active state
    Note over AD,CFG: Enablement is not conditioned on a successful test
    API-->>AD: Configuration result and applicable admin notification

    U->>API: Start voice with session, CSRF and SDP offer
    API->>CFG: Read active voice configuration
    API->>API: Reserve principal-bound lease and validate bounded SDP
    API->>RT: SDP offer, secret retained server-side
    RT-->>API: Bounded SDP answer
    API-->>U: no-store SDP and teardown token
    U->>RT: Direct WebRTC audio and data
    RT-->>U: Audio and transcript events
    U->>U: Review bounded transcript in editor
    U->>API: Submit through normal validated chat path
    U->>API: Authenticated teardown
```

Istari does not retain voice audio or SDP. Direct WebRTC means provider
retention, browser behaviour and the active session after setup remain outside
Istari's hard enforcement boundary. Text providers selected through environment
configuration may also be active at startup; the optional administrator test is
not an activation gate.

## Sources and companion records

| Concern                       | Authority                                                                                                                                                                                                                                                                                    |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Request dependencies          | [API dependencies](../../apps/api/src/coeus/api/dependencies.py)                                                                                                                                                                                                                             |
| Identity and sessions         | [Auth service](../../apps/api/src/coeus/services/auth.py), [session repository](../../apps/api/src/coeus/repositories/sessions.py), [user administration](../../apps/api/src/coeus/services/user_admin.py)                                                                                   |
| Product policy and grants     | [Store access](../../apps/api/src/coeus/services/store_access.py), [asset redemption](../../apps/api/src/coeus/services/store_asset_redemption.py), [file routes](../../apps/api/src/coeus/api/routes/store_files.py)                                                                        |
| ACG governance                | [Access service](../../apps/api/src/coeus/services/access.py), [ACG applications](../../apps/api/src/coeus/services/acg_applications.py), [ACG catalogue](../../apps/api/src/coeus/services/acg_catalogue.py)                                                                                |
| External integration controls | [AI models](../../apps/api/src/coeus/services/ai_models.py), [voice models](../../apps/api/src/coeus/services/voice_models.py), [Realtime adapter](../../apps/api/src/coeus/integrations/openai_realtime.py), [browser voice hook](../../apps/web/src/features/requests/useRealtimeVoice.ts) |
| Threat models                 | [Auth and sessions](../threat-model/auth-rbac-sessions.md), [ACG and product access](../threat-model/acg-product-access.md), [Realtime voice](../threat-model/realtime-voice.md)                                                                                                             |
