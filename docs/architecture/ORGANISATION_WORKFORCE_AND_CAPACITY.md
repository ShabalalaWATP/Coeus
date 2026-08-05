# Organisation, Workforce and Capacity Views

## Canonical calendar projection and commitments

Personal, manager, team, task, external and legacy sources converge as
canonical occurrences at the read boundary. Exact cross-source identities are
collapsed by deterministic precedence while the response retains every source.
A lower-precedence source reappears if the winning record is cancelled. A
conflicting legacy same-interval identity fails unknown instead of changing
capacity speculatively.

Team events carry one unit scope and are read through that scope. Personal and
manager events carry one owner and are projected through the owner's effective
home membership at query time. A posting boundary therefore changes projection
without copying the calendar record. Team writes require `calendar:manage` for
the target unit at preview and serialisable commit time.

Manager-created commitments have a response record distinct from the event.
Subjects acknowledge or dispute a response version; managers or authorised
successors mutate the event version. A manager change increments the response,
returns it to pending and emits a notification. This separation preserves event
authority, subject voice and original-creator provenance simultaneously.

Status: **implemented management/shadow foundation with release-gated active
authority**. These views show how users, hierarchy, calendars, work packages and
capacity fit together. They do not imply that organisation `active` mode has
been approved.

## 1. User and management view

```mermaid
flowchart LR
    accTitle: Organisation and workforce user view
    accDescr: A person has one home team, managers act through explicit scoped grants, and work, calendars and capacity are projected into authorised workspaces.

    USER["Person<br/>one effective home team"]
    PROFILE["My profile<br/>calendar + My Work"]
    LEAF["Delivery team workspace<br/>overview, board, calendar"]
    PARENT["Ancestor workspace<br/>privacy-safe aggregates"]
    ADMIN["Organisation administration<br/>tree, grants, workforce"]
    JIOC["JIOC shadow context<br/>aggregate capacity only"]

    USER --> PROFILE
    USER --> LEAF
    PROFILE -->|"one canonical event"| LEAF
    LEAF -->|"suppressed descendant totals"| PARENT
    ADMIN -->|"reviewed commands"| LEAF
    LEAF -.->|"minimised forecast"| JIOC
```

The person is never posted to two teams at once. A parent manager sees a child
only through an action-specific direct or descendant grant. Hierarchy does not
grant access to the child's tickets, products or ACGs.

## 2. Technical component view

```mermaid
flowchart TB
    accTitle: Organisation workforce technical components
    accDescr: React workspaces call narrow FastAPI services which validate current identity, grant and workflow evidence in PostgreSQL transactions.

    UI["React<br/>profile, team, routing and admin views"]
    API["FastAPI routes<br/>validated contracts + CSRF"]
    ORG["Organisation services<br/>preview + execute"]
    CAL["Calendar services<br/>series + occurrences"]
    BOARD["Board and My Work projections"]
    ASSIGN["Recommendation and assignment services"]
    POLICY["Final authority validation<br/>account + grant lineage + ticket"]

    subgraph PG["PostgreSQL transaction boundary"]
        ID[("Account projection")]
        HIER[("Units, closure, postings, grants")]
        EVENTS[("Events, exceptions, working patterns")]
        TICKET[("Authoritative ticket aggregate")]
        WORK[("Ownership, packages, dependencies")]
        CAP[("Demand holds + capacity reservations")]
        EVID[("History, command, audit, outbox")]
    end

    UI --> API
    API --> ORG
    API --> CAL
    API --> BOARD
    API --> ASSIGN
    ORG --> POLICY
    CAL --> POLICY
    BOARD --> POLICY
    ASSIGN --> POLICY
    POLICY --> ID
    POLICY --> HIER
    POLICY --> TICKET
    CAL --> EVENTS
    BOARD --> WORK
    ASSIGN --> EVENTS
    ASSIGN --> WORK
    ASSIGN --> CAP
    ORG --> EVID
    CAL --> EVID
    ASSIGN --> EVID
```

Frontend permissions control navigation only. The API service and final
PostgreSQL transaction repeat every material authority check.

## 3. Calendar projection view

```mermaid
flowchart LR
    accTitle: Canonical calendar projection
    accDescr: One event is expanded into occurrences and projected through current membership into personal, direct-team, ancestor and capacity views without copying it.

    EVENT[("Canonical event<br/>timed or all-day")]
    RULE["Daily/weekly recurrence"]
    EX["Occurrence change/cancel"]
    EXPAND["Bounded DST-safe expansion"]
    HOME["Current one-home posting"]
    PERSONAL["Personal agenda<br/>full authorised detail"]
    TEAM["Direct team<br/>redacted availability"]
    ANCESTOR["Ancestor<br/>suppressed daily aggregate"]
    FORECAST["Capacity forecast<br/>physical intervals only"]

    EVENT --> EXPAND
    RULE --> EXPAND
    EX --> EXPAND
    EXPAND --> PERSONAL
    EXPAND --> HOME --> TEAM
    HOME --> ANCESTOR
    EXPAND --> FORECAST
```

Notes and private detail do not enter capacity logic. A posting boundary changes
the projection path without copying or rewriting the event.

## 4. Assignment decision view

```mermaid
flowchart TB
    accTitle: Deterministic capacity-aware assignment decision
    accDescr: Persisted demand is matched against hard policy, capability, competency, workload, deadline and conserved capacity before a manager may accept a recommendation.

    DEMAND["Versioned demand<br/>route, capabilities, effort, deadline"]
    TEAMS["Candidate delivery leaves"]
    HARD{"Hard eligibility"}
    PEOPLE["Active Analysts<br/>one home posting"]
    FIT["Verified capability<br/>and competency"]
    CAPACITY["Working time - calendar - reservations - buffer"]
    RANK["Deterministic rank<br/>safe reasons + UUID tie-break"]
    REVIEW["Manager preview"]
    DECIDE{"Accept or<br/>reasoned soft override"}
    TX["Serialisable assignment transaction"]
    TICKET["Ticket audience + workflow leg owner"]
    PACKAGE["Accountable package"]
    RESERVE["Personal capacity reservation"]
    HUMAN["Human review"]

    DEMAND --> TEAMS --> HARD
    PEOPLE --> HARD
    HARD -->|"eligible"| FIT --> CAPACITY --> RANK --> REVIEW --> DECIDE
    HARD -->|"unknown or denied"| HUMAN
    DECIDE -->|"accepted"| TX
    DECIDE -->|"hard factor cannot be overridden"| HUMAN
    TX --> TICKET
    TX --> PACKAGE
    TX --> RESERVE
```

JIOC may use aggregate team feasibility for routing, but it does not select a
named person. The accepting manager remains accountable for the decision.

## 5. Work ownership and transfer view

```mermaid
sequenceDiagram
    accTitle: Controlled work ownership and transfer
    accDescr: A source manager proposes a work transfer, the target manager reviews current evidence, and one transaction moves ownership and reservations without moving the person.

    actor Source as Source manager
    participant API as Transfer service
    participant PG as PostgreSQL
    actor Target as Target manager

    Source->>API: Preview target and package dispositions
    API->>PG: Read ticket, ownership, grants, packages, participants, reservations
    PG-->>API: Version-bound impact
    API-->>Source: Reviewed preview
    Source->>API: Propose exact preview
    API->>PG: Persist expiring proposal and audit
    Target->>API: Accept or reject
    API->>PG: Revalidate both managers and all current evidence
    alt accepted
        PG->>PG: Move workflow-leg ownership
        PG->>PG: Apply every named package disposition
        PG->>PG: Revoke source participants and replace holds/reservations
        PG->>PG: Append history, command, audit and outbox
        PG-->>Target: Committed result
    else rejected, expired or stale
        PG->>PG: Preserve current ownership and close proposal
        PG-->>Target: Safe non-mutating outcome
    end
```

This transfer moves work only. It never creates a second personnel posting and
never expands ticket, ACG, product or asset access.

## 6. Runtime and cutover states

```mermaid
stateDiagram-v2
    accTitle: Organisation runtime modes
    accDescr: Disabled preserves the established runtime, shadow compares evidence, management enables reviewed tools, and active requires an exact approved release manifest.

    [*] --> Disabled
    Disabled --> Shadow: projection configured
    Shadow --> Management: administration enabled
    Management --> ActiveCandidate: local gates pass
    ActiveCandidate --> Management: evidence stale or rejected
    ActiveCandidate --> Active: exact candidate approved
    Active --> Active: forward repair and monitored operation
```

`ActiveCandidate` is a release concept, not a runtime mode. Active composition
must remain unavailable until the immutable evidence record binds the exact
schema, projection hashes, routing evaluation, protected checks and approval.

## 7. Security boundaries

- Account suspension, grant revocation and ticket audience loss take effect at
  the final read or transaction boundary.
- Current policy governs historical views. Restored historical rows never
  restore revoked authority.
- Parent workspaces use aggregates and complementary suppression. They do not
  enumerate sibling personnel or private events.
- Recommendation exclusions are coarse. Calendar notes, biographies,
  clearance details and sensitive failure reasons do not enter prompts or logs.
- Every mutation is actor-scoped, version-bound and idempotent, with immutable
  history, audit and outbox evidence committed atomically.
