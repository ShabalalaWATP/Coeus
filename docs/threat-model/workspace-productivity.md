# Workspace productivity threat model

## Assets and boundaries

Protected assets are personal board preferences, manager-owned templates,
work-update existence, task identifiers and links to Intelligence Store
objects. The principal trust boundaries are the browser/API boundary, current
organisation authority in PostgreSQL and the independently authoritative Store
project and product services.

## Threats and controls

| Threat | Control |
| --- | --- |
| A saved filter reveals a revoked child team or task. | Every list rechecks the active account, current `workspace:view` lineage and board authority. Revoked records are omitted. |
| One user reads or mutates another user's preference or update. | APIs derive the actor from the session. Rows are actor scoped and mutations check ownership. Inaccessible IDs return generic not-found. |
| A stale manager edits a shared template. | Commands bind the current `workspace:configure` grant ID/version and aggregate version in a serialisable transaction. |
| Duplicate delivery creates repeated inbox entries. | Recipient/event keys are unique. Actor-scoped request hashes make command replay idempotent and reject key reuse with different input. |
| An update becomes an object-existence oracle. | Responses omit producer keys and recipients. Reads recheck the current object, team and action boundary before returning an allowlisted payload. |
| A Store link grants access or survives target revocation. | Links are opaque references, not grants. Creation resolves the current Store policy. Listing resolves it again and hides failures. Opening uses the existing policy-enforcing Store route. |
| A cross-store failure creates authority drift. | The relational commit and Store read are intentionally not one transaction because no Store authority is copied or changed. A dangling reference is harmless and remains hidden until it resolves lawfully. |
| Oversized queries exhaust the service. | Filter cardinalities, text sizes, candidate scans and keyset pages are bounded. |
| A mutation lacks evidence. | Commands, audit events and outbox events commit together. Command rows are immutable. |

## Residual risks

A Store target may be revoked between its creation-time policy check and the
relational link commit. The link grants nothing and its next projection performs
a fresh target check, so the maximum exposure is a hidden dangling identifier.
Display labels are stored for usability but are never returned without current
target access. Automated notification dispatch remains an operational concern;
the durable inbox and preferences are authoritative when delivery is delayed.
