# Deployment and Operations Views

Status: local views are **implemented**. Cloud paths are **future gated** unless
explicitly marked as Terraform-created resources. Verified against `e44b66b6`
on 23 July 2026.

## 1. Supported local modes

The browser always fetches the SPA and calls the configured API origin
separately. nginx does not proxy API traffic.

```mermaid
flowchart TB
    accTitle: Supported local hybrid and Compose modes
    accDescr: A browser independently reaches the web and API origins; the API runs as one process and uses PostgreSQL plus a local object directory, while MinIO is unused scaffolding.

    B["Browser"]

    subgraph hybrid["Default hybrid development"]
        VITE["Host Vite process"]
        UV["Host Uvicorn<br/>one process, one worker"]
        PG1[("Compose PostgreSQL + pgvector")]
        FS1[["Host local object root"]]
        B -->|"HTML, JS and CSS"| VITE
        B -->|"configured API origin"| UV
        UV --> PG1
        UV --> FS1
    end

    subgraph full["Optional full Compose"]
        WEB["nginx web container<br/>SPA only"]
        API["API container<br/>one process, one worker"]
        PG2[("PostgreSQL + pgvector")]
        FS2[["Named local-object volume"]]
        MINIO[["MinIO<br/>UNUSED parity scaffolding"]]
        B -->|"HTML, JS and CSS"| WEB
        B -->|"configured API origin"| API
        API --> PG2
        API --> FS2
        MINIO -.->|"not wired"| API
    end
```

The supported API topology is one process, one worker and one replica.
Identity, configuration and other bounded JSON namespaces plus local object
bytes still require the single-writer constraint.

## 2. Future GCP resource shell

Terraform can create this resource shell, but the application cannot yet run
with its configured GCS and Pub/Sub paths. Runtime readiness rejects those
unimplemented adapters.

```mermaid
flowchart TB
    accTitle: Future-gated Google Cloud resource shell
    accDescr: Terraform-created Cloud Run, Cloud SQL, buckets, Pub/Sub, Artifact Registry, secrets and identity resources are separated from missing runtime adapters and an unimplemented deploy path.

    U["Users"]
    GH["GitHub Actions<br/>validation workflows"]
    DEPLOY["FUTURE GATED<br/>no cloud deployment job"]
    WIF["Terraform-created<br/>Workload Identity Federation"]
    AR["Artifact Registry<br/>CMEK attached"]
    KMS["Cloud KMS"]

    subgraph run["Terraform-created Cloud Run services"]
        WEB["Web service"]
        API["API service"]
        GATE["Runtime security gate"]
    end

    SQL[("Cloud SQL PostgreSQL<br/>provider-default encryption")]
    BUCKET[["Cloud Storage buckets<br/>provider-default encryption"]]
    PUB[["Pub/Sub topics and dead letters<br/>CMEK attached"]]
    SM["Secret Manager placeholders<br/>values supplied out of Terraform"]
    GCSAD["MISSING<br/>GCS object adapter"]
    PSAD["MISSING<br/>Pub/Sub runtime adapter"]

    U -->|"fetch SPA"| WEB
    U -->|"configured API origin"| API
    GH --> WIF
    GH -.-> DEPLOY -.-> AR
    KMS --> AR
    KMS --> PUB
    AR -.-> run
    API --> GATE
    GATE -->|"implemented"| SQL
    GATE --> SM
    GATE -.->|"startup rejected"| GCSAD -.-> BUCKET
    GATE -.->|"startup rejected"| PSAD -.-> PUB
```

Cloud-creating plans and applies require the ADR 0019 readiness acknowledgement.
Targeted Terraform operations remain prohibited. A future runtime must also
close identity, object storage, backup, audit export, monitoring and
multi-replica boundaries.

## 3. Current operational signals

```mermaid
flowchart LR
    accTitle: Current application observability and assurance signals
    accDescr: API requests produce bounded JSON logs and request IDs, health routes expose liveness and database-only readiness, protected metrics expose cached admission and outbox state, and audit is separate evidence.

    API["FastAPI process"]
    LOG["JSON stdout<br/>request ID, route, status, duration"]
    LIVE["/health/live<br/>process liveness"]
    READY["/health/ready<br/>PostgreSQL only"]
    METRIC["/api/v1/metrics<br/>cached admission + outbox snapshot"]
    AUTH["Hosted bearer token<br/>private ingress still required"]
    AUDIT[("Audit events<br/>security and business evidence")]
    OP["Operator or platform collector"]
    MISSING["NOT IMPLEMENTED IN REPO<br/>trace collector, log sink,<br/>dashboard or alert resources"]
    BLIND["NOT COVERED BY READINESS<br/>objects, indexes, providers,<br/>outbox delivery and SMTP"]

    API --> LOG --> OP
    API --> LIVE --> OP
    API --> READY --> OP
    READY -.-> BLIND
    API --> METRIC
    AUTH --> METRIC --> OP
    API --> AUDIT
    OP -.-> MISSING
```

Audit evidence is not telemetry. Operators must supply retention, dashboards,
alerts and incident routing in the deployment environment. Hosted metrics fail
startup without a strong bearer token, and that route should remain on private
monitoring ingress.

## 4. Durable effect and recovery path

```mermaid
stateDiagram-v2
    accTitle: Workflow outbox delivery and operator recovery
    accDescr: A committed intent is claimed by the hosted in-process dispatcher, settles idempotently, retries with bounded attempts, or enters an operator-investigated dead letter that reuses the same event identity.

    [*] --> Pending: workflow commit
    Pending --> Claimed: fenced bounded claim
    Claimed --> Delivered: idempotent handler succeeds
    Claimed --> Retrying: bounded failure
    Retrying --> Claimed: available_at reached
    Retrying --> DeadLetter: attempt ceiling
    DeadLetter --> Pending: authorised reasoned replay
    Delivered --> [*]
```

Claims use `FOR UPDATE SKIP LOCKED`, an opaque worker identity and an expiry.
Monitor availability, oldest pending age, retrying and dead-letter counts.
Replay is RBAC-protected and audited. It retains the event ID so handler
idempotency remains meaningful.

There is a current local relational limitation: release-notification intents
are committed, but the dispatcher is installed only in hosted composition.
Those local intents can remain pending. Registration, ACG, assignment and
rework workflows are dashboard-driven and do not promise notifications.

## 5. CI and release assurance

```mermaid
flowchart TB
    accTitle: Independent CI and production release assurance
    accDescr: Pull requests run independent quality, test and security workflows; passing CI supports review and merge but production still requires authorised staging and a sealed deep scan of the exact candidate.

    CHANGE["Pull request or push"]
    BACK["Backend CI<br/>lines, docs, format, lint, types,<br/>architecture, tests, coverage, Bandit, audit"]
    FRONT["Frontend CI<br/>format, lint, types, dead code,<br/>tests, audit, build and Playwright"]
    STATIC["CodeQL + Semgrep"]
    SUPPLY["Secret scan + SBOM"]
    IMAGE["API and web image builds<br/>Trivy scans"]
    IAC["Terraform validation<br/>Checkov"]
    DAST["Local unauthenticated<br/>ZAP baseline"]
    PROTECT["Repository branch protection<br/>external configuration"]
    MERGE["Reviewed immutable revision"]
    STAGE["Authorised staging verification"]
    DEEP["Fresh sealed whole-repository deep scan<br/>exact immutable release candidate"]
    PROD["Production-release decision"]

    CHANGE --> BACK
    CHANGE --> FRONT
    CHANGE --> STATIC
    CHANGE --> SUPPLY
    CHANGE --> IMAGE
    CHANGE --> IAC
    CHANGE --> DAST
    BACK --> PROTECT
    FRONT --> PROTECT
    STATIC --> PROTECT
    SUPPLY --> PROTECT
    IMAGE --> PROTECT
    IAC --> PROTECT
    DAST --> PROTECT
    PROTECT --> MERGE
    MERGE --> STAGE --> DEEP --> PROD
```

These workflows are independent and branch protection is managed in GitHub,
not in repository code. ZAP is a local unauthenticated baseline. CI success is
not production accreditation.

## 6. Coordinated logical recovery

```mermaid
flowchart TB
    accTitle: Coordinated PostgreSQL and local-object recovery drill
    accDescr: Quiesced writers produce two matching inventories, an allowlisted database and object bundle restores into empty targets, authority is validated, derived search is rebuilt, and current draft-object validation remains a limitation.

    STOP["Stop API writers and dispatcher"]
    REV["Confirm checkout and database<br/>Alembic heads match"]
    SNAP1["Database export + complete object inventory"]
    SNAP2["Second export and inventory"]
    MATCH{"Digests match?"}
    BUNDLE["Publish manifest-bound bundle<br/>key retained separately"]
    TARGET["Migrate empty database<br/>and require empty object root"]
    IMPORT["One database import transaction<br/>and staged object rename"]
    VALIDATE["Validate ticket hashes, audiences,<br/>Store assets and cleared claims"]
    GAP["LIMITATION<br/>validation compares all objects only<br/>to Store asset rows; retained draft bytes can fail"]
    REINDEX["Rebuild and verify grounded index<br/>derived search tables are excluded"]
    RESUME["Operator acceptance<br/>then resume writers"]

    STOP --> REV --> SNAP1 --> SNAP2 --> MATCH
    MATCH -->|"no"| STOP
    MATCH -->|"yes"| BUNDLE --> TARGET --> IMPORT --> VALIDATE
    VALIDATE -.-> GAP
    VALIDATE --> REINDEX --> RESUME
```

The drill is application-level recovery evidence, not a replacement for a
managed or physical backup test. Until draft-object validation is broadened,
operators must use the runbook's documented precondition and must not claim
complete recovery of retained `workflow/submissions/...` bytes.

## Sources and companion records

| Concern                   | Authority                                                                          |
| ------------------------- | ---------------------------------------------------------------------------------- |
| Local composition         | `docker-compose.yml`, `scripts/dev.ps1`, `infra/docker/nginx-web.conf`             |
| GCP resource shell        | `infra/gcp`, [ADR 0019](../adr/0019-current-local-runtime-future-gcp-migration.md) |
| Runtime gating            | `apps/api/src/coeus/core/runtime_security.py`, `services/object_storage.py`        |
| Signals and outbox        | `core/logging.py`, `api/routes/health.py`, `services/outbox_dispatcher.py`         |
| CI and security workflows | `.github/workflows`                                                                |
| Recovery                  | [Coordinated backup and restore](../runbooks/coordinated-backup-restore.md)        |
| Deployment guide          | [Concise deployment architecture](../ARCHITECTURE_DEPLOYMENT.md)                   |
