# ADR 0046: Automatic local retrieval rebuilds

## Status

Accepted

## Context

Corpus identity already detects product and asset changes, but detection alone
leaves semantic retrieval stale until an administrator manually starts a job.
The rebuild implementation is a bounded, process-local shadow-generation worker.

## Decision

Install one application-owned coordinator around the existing indexing service.
Store mutation callbacks and retrieval configuration changes enqueue work. The
coordinator debounces signals, serialises rebuilds and checks corpus identity
again after each run. Startup also queues stale or unindexed state, providing
recovery when a process stopped between persistence and notification.

The existing shadow generation, validation and atomic promotion rules remain
the authority. Notification is best effort; corpus comparison is the durable
source of truth. Hosted multi-replica scheduling remains unsupported until a
durable distributed job claim is designed.

## Consequences

- Local Store changes become searchable without an administrative action.
- Bursts of seed or workflow writes produce one rebuild rather than one per row.
- A provider failure leaves the previous generation available and records the
  bounded failure state.
- The administration page polls queued and running work, uses plain-language
  states and exposes a retry action only after automatic recovery fails.
- Hosted scale-out must keep this coordinator disabled until distributed job
  ownership is implemented.
