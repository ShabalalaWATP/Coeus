# ADR 0033: Encrypted Administrator Integration Credentials

## Status

Accepted.

## Context

Provider model choices were durable, but the active text provider and every
administrator-entered text or Realtime voice API key were process memory only.
Restarting the API therefore disabled integrations and forced an administrator
to paste credentials again. Persisting plaintext keys in the generic state
store would expose them to database, fallback-file and backup readers.

## Decision

- Persist the active text provider, every provider's selected model, the
  selected Realtime model and the voice enabled state.
- Store each administrator-entered credential in a separate state namespace as
  a versioned AES-256-GCM envelope. Bind authenticated additional data to the
  exact logical provider identity so text OpenAI, Realtime OpenAI and other
  provider ciphertext cannot be substituted for one another.
- Keep the configuration-encryption key outside the state store. Local mode
  creates it in the ignored configuration-key path with owner-only permissions;
  Docker keeps that path in the API local-data volume, separate from PostgreSQL.
  Hosted environments must supply `COEUS_CONFIGURATION_ENCRYPTION_KEY` from a
  secret manager.
- Keep environment-managed provider keys authoritative and reject replacement
  through the admin API. Never copy environment keys into application state.
- Fail startup closed if a stored envelope is malformed, tampered with or
  cannot be decrypted. Do not migrate or trust legacy plaintext key fields.
- Preserve audited-change compensation: a failed persistence or audit step
  restores the previous runtime and encrypted credential state.

## Consequences

API restarts no longer clear administrator-entered credentials or provider and
model choices. Admin reads still expose only `apiKeyConfigured`, while audit
events contain provider metadata and no key material.

The configuration-encryption key is now part of recovery. Database or fallback
state backups are insufficient without a separately protected copy of that key.
Changing or losing it makes encrypted credentials unavailable; the first
implementation deliberately fails closed and requires restoring the original
key or explicitly clearing and re-entering credentials. Online key rotation is
future work.
