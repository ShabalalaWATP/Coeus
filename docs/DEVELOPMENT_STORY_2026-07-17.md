# Coeus Development Story: 2026-07-17

## Admin command centre and operational analytics

- Converted access requests, text AI, independent search embeddings and
  optional Realtime voice settings into compact accessible disclosures with
  visible provider, key, activation and index state.
- Standardised configuration controls and made the distinction between a saved
  key, an active capability and a successful connection test explicit.
- Added a bounded, administrator-only OpenAI Realtime connection test without
  enabling voice or exposing the server-held credential.
- Added admin-only return navigation across Access Groups, Analytics, Audit,
  Users and Store.
- Separated admin platform analytics from operational intelligence analytics.
  Admin now sees aggregate account, access, AI service, search, voice, audit
  and process health without ticket, product, query, user or audit metadata;
  RFA and Collection retain their authorised workflow and reuse views.
- Scoped successful connection-test status to the saved provider/model and
  cleared stale results whenever an administrator edits a key or model draft.
- Verified 507 frontend tests at 98.69 per cent line and 95.05 per cent branch
  coverage, plus 1,072 non-PostgreSQL and 70 real-PostgreSQL backend tests at
  98.08 per cent line and 95.08 per cent branch coverage. Static, contract and
  live browser acceptance checks also passed.
