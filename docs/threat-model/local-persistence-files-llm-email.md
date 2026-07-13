# Local Persistence, Files, LLM And Email Threat Model

## Scope

PostgreSQL state store, explicit file-store fallback, real Store asset
upload/download, optional LLM providers and optional SMTP delivery.

## Assets

- PostgreSQL `coeus_state` payloads, Intelligence Store relational tables and
  explicit fallback JSON state files.
- Uploaded product asset bytes under `.local-data/objects` or the Docker
  object-data volume.
- Signed asset download tokens.
- Runtime LLM provider keys, prompts and untrusted model-catalogue metadata.
- SMTP credentials and outbound release emails.

## Threats And Controls

| Threat                                                                                                                  | Control                                                                                                                                                                                                                                           |
| ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Deserialisation restores arbitrary Python objects.                                                                      | Persistence uses an allow-listed JSON codec for known domain dataclasses and enums only, not pickle or dynamic imports.                                                                                                                           |
| Python module renames make persisted identities unstable or permit unexpected restoration.                              | Writers use semantic stable IDs from a committed allow-list. Readers retain explicit legacy-ID compatibility for the rollback window, reject unknown IDs, and reject payloads carrying both identity formats.                                      |
| Search indexes, relational mirrors or semantic labels bypass Store access policy.                                       | Relational Store tables and indexes are persistence primitives only; application access still filters by RBAC, clearance, status and at least one active shared ACG before ranking or detail responses.                                           |
| A committed local database, fallback state file or secret leaks sessions, synthetic tickets, API keys or audit data.    | `.local-data/` and `.env` are gitignored; docs keep PostgreSQL local and secrets out of committed files. UI-entered provider keys are runtime-only and not written to `coeus_state`; legacy persisted keys are scrubbed on startup.               |
| Retired workspace payloads in older local state restore removed authorisation paths.                                    | Alembic removes known retired workspace payloads from PostgreSQL state snapshots. The codec only accepts current domain dataclasses and enum values, so any remaining retired records or permissions fail closed during decode.                   |
| A ticket shadow silently diverges during relational migration, or stale processes overwrite a winner.                   | The default relational adapter writes one versioned aggregate and uniquely keyed outbox event per transaction. Hash predicates provide cross-process compare-and-swap. Two clean candidate validations preceded cutover; `shadow_validate` fails closed on disagreement and `legacy` remains an explicit rollback mode. |
| Uploaded filenames escape the local object root.                                                                        | Object keys are split into safe path segments, resolved under the configured root and rejected if they escape that root.                                                                                                                          |
| Object storage failure leaves searchable metadata or false audit evidence for missing asset bytes.                      | Upload creates the product record without `product_created`, writes bytes, then records the audit event. Storage failure rolls back the product and returns `asset_storage_failed`; audit failure rolls back both the product and uploaded bytes. |
| A local reset deletes object bytes but leaves PostgreSQL metadata, causing placeholder substitution or broken recovery. | The documented reset helper stops the stack and removes PostgreSQL and the selected local object store together; it refuses to run without an explicit destructive confirmation and never recommends object-only deletion.                        |
| A forged or reused download token exposes another product.                                                              | Tokens are HMAC signed, expire, bind user, product and asset IDs, and redemption re-checks Store visibility before returning bytes.                                                                                                               |
| Client-provided file metadata lies about size or hash, or unauthenticated multipart bodies consume memory and disk.     | Authentication and CSRF checks run before multipart parsing. Wire bytes, staged bytes, concurrent uploads, per-user work and total worst-case in-flight bytes are bounded; size and SHA-256 are computed while streaming to a temporary file.       |
| LLM prompts leak hidden state or grant authority.                                                                       | The provider sends only extracted intake fields and safety flags, asks for one concise requester-facing sentence and keeps mock as the offline default.                                                                                           |
| Provider credentials leak through admin reads, audit records or database backups.                                       | The admin API accepts keys but returns only `apiKeyConfigured`; audit records only provider/model metadata. Persistent credentials must come from environment configuration or a future secret manager, not generic app state.                    |
| A malicious or malformed provider catalogue injects control characters or unbounded state.                              | Discovery accepts only bounded model IDs, caps persisted entries, rejects invalid or empty response shapes, revalidates restored state and never logs response bodies or keys.                                                                    |
| Refresh removes a custom or active model and changes behaviour after restart.                                           | Custom and discovered IDs are persisted separately; refresh is append-only and never changes the active model. Adding a custom ID also requires a separate explicit Apply action.                                                                 |
| Slow provider discovery or connection testing stalls every API request.                                                 | Both synchronous outbound admin operations run in FastAPI's worker thread pool and retain bounded timeouts.                                                                                                                                       |
| One principal exhausts operator-funded LLM or retained-ticket capacity.                                                  | External assistant calls reserve principal and deployment capacity before provider acquisition. Sliding-window and concurrency ceilings are bounded, failed calls refund their reservation, and new retained tickets have atomic principal and deployment admission. |
| Similar-request scoring fans out one embedding call per retained ticket.                                                 | Query and immutable candidate embeddings use normalised single-flight caching. Candidates are deterministically pre-ranked and semantic work stops at a fixed 32-candidate budget.                                                               |
| Multiple API processes bypass local upload, search or ticket ceilings.                                                    | Hosted upload, Store, RFI and similarity work uses expiring PostgreSQL leases with atomic deployment, principal, concurrency and unit checks. Ticket creation also allocates references under the shared database lock. Denied work is rejected before provider, worker or multipart acquisition. |
| A workflow relationship grants draft access after reassignment or deactivation.                                          | Versioned ticket writes transactionally rebuild the indexed product/principal/reason audience projection. Linked-product reads require the persisted assigned-analyst relationship; inactive assignments are removed immediately. Creator and privileged-role decisions still re-check current product and account state. |
| Failed model configuration leaves an external provider enabled after a rejected admin request.                          | Model selection, catalogue changes and API key configuration restore the previous runtime provider, model, catalogues, key and change metadata if persistence or audit recording fails.                                                           |
| SMTP credentials are logged or committed.                                                                               | `.env` is ignored, `.env.example` contains names only, and delivery audits record user ID and subject only, not passwords or message bodies.                                                                                                      |
| SMTP outage breaks the release workflow after partial state changes.                                                    | Email delivery failures are audited as `email_delivery_failed`; in-app notifications and the outbox remain the durable record.                                                                                                                    |

## Open Risks

- Provider, upload and retained-ticket admission is process-local in this
  tactical phase. Hosted multi-instance operation remains disallowed until the
  shared PostgreSQL reservation ledger in ADR 0025 is implemented.
- Upload malware scanning, content inspection and MIME verification remain
  deferred before any untrusted or production file handling.
- External LLM use sends extracted request text to the selected provider. Keep mock
  mode for offline or sensitive demos unless the data is authorised for that
  provider.
