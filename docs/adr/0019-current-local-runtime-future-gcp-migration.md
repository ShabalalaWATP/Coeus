# ADR 0019: Current Local Runtime And Future GCP Migration

## Status

Accepted.

## Context

Coeus contains a GCP deployment reference, but its current repositories,
sessions, rate limits and audit state are designed for one local API writer.
Treating the reference as an active deployment target creates an unsafe mismatch
between state semantics and possible Cloud Run replica count.

## Decision

- The supported current runtime is local and single-instance.
- Local PostgreSQL and local file/object-storage adapters remain authoritative.
- GCP Terraform, workflows and runbooks are future migration reference material,
  not a supported deployment target.
- The GitHub migration workflow validates Terraform and builds images locally;
  it has no cloud authentication, push or deployment step.
- Terraform apply is blocked by a default-deny migration-readiness precondition.
- The reference configuration permits one API writer until sessions, rate
  limits, registration capacity and audit evidence use shared transactional or
  append-only controls suitable for distributed execution.
- Cloud-specific adapters must remain behind explicit integration protocols and
  may not leak into domain services.

## GCP Readiness Gates

The future path cannot be activated until all of the following are verified:

1. Row-level transactional session and revocation storage.
2. Distributed atomic rate limiting and registration capacity.
3. Append-only externally retained audit evidence.
4. Implemented and tested GCS and Pub/Sub adapters.
5. Authorised staging validation of Terraform, identity, traffic and rollback.
6. A fresh threat model and security scan against the migration revision.

## Consequences

- Local development and delivery do not require GCP credentials or services.
- The existing infrastructure design remains useful without implying current
  production readiness.
- Horizontal API scaling is intentionally unavailable until its security
  invariants are implemented rather than merely documented.
