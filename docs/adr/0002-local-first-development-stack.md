# ADR 0002: Local-first Development Stack

## Status

Accepted.

## Context

Coeus must run locally without Google Cloud access, while keeping cloud services behind interfaces for later GCP and air-gapped deployments.

## Decision

Sprint 1 uses Docker Compose for local infrastructure:

- PostgreSQL with pgvector for the database.
- MinIO for local object storage.
- API and web services wired to the local network.

Future GCP-specific implementations must live under explicit integration modules rather than domain services.

## Consequences

- Developers can run tests and the local shell without cloud credentials.
- Object storage and database choices are visible early.
- Terraform and workload identity can be added later without changing domain code.

