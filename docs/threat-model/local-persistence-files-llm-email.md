# Local Persistence, Files, LLM And Email Threat Model

## Scope

PostgreSQL state store, explicit file-store fallback, real Store asset
upload/download, Gemini API integration and optional SMTP delivery.

## Assets

- PostgreSQL `coeus_state` payloads, Intelligence Store relational tables and
  explicit fallback JSON state files.
- Uploaded product asset bytes under `.local-data/objects` or the Docker
  object-data volume.
- Signed asset download tokens.
- Gemini API key and prompts sent to the external model provider.
- SMTP credentials and outbound release emails.

## Threats And Controls

| Threat | Control |
| --- | --- |
| Deserialisation restores arbitrary Python objects. | Persistence uses an allow-listed JSON codec for known domain dataclasses and enums only, not pickle or dynamic imports. |
| Search indexes, relational mirrors or semantic labels bypass Store access policy. | Relational Store tables and indexes are persistence primitives only; application access still filters by RBAC, clearance, status and at least one active shared ACG before ranking or detail responses. |
| A committed local database, fallback state file or secret leaks sessions, synthetic tickets, API keys or audit data. | `.local-data/` and `.env` are gitignored; docs keep PostgreSQL local and secrets out of committed files. UI-entered Gemini keys are runtime-only and not written to `coeus_state`; legacy persisted keys are scrubbed on startup. |
| Uploaded filenames escape the local object root. | Object keys are split into safe path segments, resolved under the configured root and rejected if they escape that root. |
| Object storage failure leaves searchable metadata or false audit evidence for missing asset bytes. | Upload creates the product record without `product_created`, writes bytes, then records the audit event. Storage failure rolls back the product and returns `asset_storage_failed`; audit failure rolls back both the product and uploaded bytes. |
| A forged or reused download token exposes another product. | Tokens are HMAC signed, expire, bind user, product and asset IDs, and redemption re-checks Store visibility before returning bytes. |
| Client-provided file metadata lies about size or hash. | Upload computes size, MIME fallback and SHA-256 server-side after enforcing `COEUS_LOCAL_UPLOAD_MAX_BYTES`. |
| Gemini prompts leak hidden state or grant authority. | The provider sends only extracted intake fields and safety flags, asks for one concise requester-facing sentence and keeps mock as the offline default. |
| Gemini credentials leak through admin reads, audit records or database backups. | The admin API accepts the key but returns only `apiKeyConfigured`; audit records only provider/model metadata. Persistent Gemini credentials must come from environment configuration or a future secret manager, not generic app state. |
| Failed model configuration leaves Gemini enabled after a rejected admin request. | Model selection and API key configuration restore the previous runtime provider, model, key and change metadata if persistence or audit recording fails. |
| SMTP credentials are logged or committed. | `.env` is ignored, `.env.example` contains names only, and delivery audits record user ID and subject only, not passwords or message bodies. |
| SMTP outage breaks the release workflow after partial state changes. | Email delivery failures are audited as `email_delivery_failed`; in-app notifications and the outbox remain the durable record. |

## Open Risks

- Upload malware scanning, content inspection and MIME verification remain
  deferred before any untrusted or production file handling.
- Gemini API use sends extracted request text to an external provider. Keep mock
  mode for offline or sensitive demos unless the data is authorised for that
  provider.
