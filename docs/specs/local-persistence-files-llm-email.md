# Local Persistence, Files, LLM And Email Spec

## Goal

Make the app locally durable and integration-ready without requiring GCP
hosting, GCS, Pub/Sub or Vertex AI.

## Scope

- PostgreSQL state store for local development and the Docker local stack.
- Relational Intelligence Store schema for products, assets, ACG joins,
  semantic labels, full-text search and pgvector-ready embeddings.
- File state store retained only as an explicit fallback.
- Local object storage for real Store upload and download bytes.
- Signed, expiring asset download tokens that re-check user, product and asset.
- Admin-managed Gemini model selection and runtime Gemini API key input that
  affect future agent calls app-wide without exposing the key back to the
  browser. Model selection is persisted; UI-entered keys are runtime-only.
- Optional SMTP email delivery behind the existing notification outbox.

## Acceptance Criteria

- Restarting the API with `COEUS_PERSISTENCE_PROVIDER=postgres` keeps users,
  sessions, access state, tickets, Store records, notifications and audit
  events.
- Local and Docker app modes store app state in PostgreSQL.
- PostgreSQL startup and Alembic migrations create the Intelligence Store
  relational schema alongside the compatibility state table.
- Store product saves mirror product metadata, assets, ACG joins and semantic
  labels into the relational Intelligence Store tables when PostgreSQL
  persistence is active.
- Store list, detail and reference-generation paths refresh from the relational
  Store tables when PostgreSQL persistence is active, rather than relying only
  on a start-up snapshot.
- Store search uses PostgreSQL-side visibility and metadata predicates for
  shared ACG, clearance, draft visibility, full-text query, owner/team, status,
  type, source, region, tag, project and date filters, then the service rechecks
  the normal access policy before counts, facets or results are returned.
- Store product detail and asset-download grant paths also use PostgreSQL-side
  visible-product lookups before the normal API policy recheck.
- Product upload accepts one real asset, computes its size and SHA-256 hash
  server-side, stores bytes locally and allows authorised token redemption.
- Seeded synthetic products have local placeholder bytes so demo downloads work.
- Admin-configured Gemini model choices are persisted and audited. UI-entered
  Gemini keys are hidden from responses, held only in the running API process
  and used by future assistant calls for every user until restart.
- `COEUS_EMAIL_PROVIDER=smtp` sends through SMTP when configured; the default
  outbox records and audits emails without external delivery.

## Non-Goals

- Cloud SQL, GCS, Pub/Sub, Cloud Run or Vertex AI deployment.
- Malware scanning of uploaded files.
- Multi-file upload batches.
- Production email bounce handling or unsubscribe workflows.
