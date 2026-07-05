# ADR 0008: Local-First RFI Search Agent

## Status

Accepted

## Context

Sprint 7 requires full-text search, pgvector-style semantic search, hybrid
ranking and product-offer handling. The current Coeus implementation is still a
local-first in-memory architecture. Earlier ADRs intentionally kept repository,
access-policy and service boundaries in place so PostgreSQL, pgvector and
object storage can be introduced without rewriting route handlers or UI flows.

## Decision

Implement the Sprint 7 RFI Search Agent as a service layer that consumes the
existing Intelligence Store search and detail services. The agent performs:

- requester-based access filtering before ranking;
- deterministic token full-text scoring;
- deterministic token-vector semantic similarity;
- hybrid score blending and match explanations;
- offer persistence on the ticket record;
- accept, reject, dissemination and audit events.

The semantic scorer is named and isolated as an adapter boundary. It is not a
production embedding model and does not claim to persist pgvector embeddings.
When the database persistence sprint lands, PostgreSQL full-text search and
pgvector similarity can replace these adapters while preserving the RFI Search
Agent contract and tests.

## Consequences

- Sprint 7 remains runnable without cloud services, credentials or real data.
- Security tests can verify count leakage, ACG filtering and clearance filtering
  before database persistence exists.
- Search quality is deterministic and suitable for regression tests, but not a
  substitute for production embedding quality.
- The future database adapter must keep the same invariant: filter by requester
  access before returning product IDs, counts, facets or offers.
