# Retrieval administration and demo-index reliability remediation

## Status

Accepted for implementation, 1 August 2026.

## Problem

The independent retrieval controls expose the correct separation from chat and
voice, but the workflow is harder to understand than the AI provider controls.
In particular, the connection-test endpoint tests only the already-active
provider. An administrator can therefore select Gemini in the form while a
successful test still validates the offline mock.

The local demo corpus also creates false operational warnings. Base catalogue
products receive a new `updated_at` value on every process start, so an
unchanged corpus is reported as stale. Their declared asset hashes and sizes do
not match the placeholder objects written to storage. Persisted stress-test
products can add thousands of further integrity warnings. These conditions
make the search status noisy and hide genuine extraction failures.

## User outcome

An administrator can follow one explicit provider, model, test, apply and
rebuild workflow. The test result identifies exactly the draft provider and
model that were tested. A local restart does not invalidate an unchanged demo
corpus, and generated demo assets have truthful integrity metadata.

## Functional contract

### Provider and model workflow

- Present retrieval providers as labelled choices using the same visual and
  interaction hierarchy as the AI provider panel.
- Show the dedicated Gemini key only when Gemini is selected. The key remains
  encrypted, write-only and independent from chat and voice credentials.
- Present the models available for the selected provider as radio-card choices.
- Test the selected draft provider and model before applying it. The test API
  accepts the provider, model and explicit external-egress confirmation.
- A successful test is scoped to the exact provider and model. Changing either,
  saving a key or receiving a failed test clears that success.
- Gemini testing and activation both require a saved dedicated key and explicit
  egress confirmation. The test sends only the fixed synthetic connection-test
  phrase. It does not send Store documents.
- Applying an unchanged provider and model is disabled. Applying a changed
  configuration is enabled only after that exact configuration passes a test.
- Rebuilding remains a separate, explicit operation against the active
  configuration. Its status and result remain observable in place.
- The status label reports indexed request vectors, not all active requests.

### Demo corpus stability and asset integrity

- An unchanged deterministic seed product preserves its existing creation and
  update timestamps during an upsert and does not cause a persistence write.
- A real seeded-content change preserves the original creation timestamp but
  receives a new update timestamp, so the corpus becomes stale for a valid
  reason.
- Base demo assets are generated deterministically. Their declared byte length
  and SHA-256 hash exactly match the stored object.
- Demo PDFs are syntactically valid PDFs. Supported text and structured assets
  contain bounded synthetic content suitable for local retrieval testing.
- Unsupported asset formats may remain visible as accurately categorised
  extraction warnings. Missing or integrity-mismatch warnings must not be
  manufactured by the normal demo seed path.
- Existing local stress-test products are removed only by exact product
  identity after a recoverable database backup. No title- or reference-based
  boot-time deletion is introduced.

### Generation integrity and interrupted jobs

- The corpus version hashes canonical metadata-index content, asset identity,
  MIME type, byte length, asset hash, extractor version and chunker version.
  Lifecycle timestamps are not retrieval inputs and must not alter the hash.
- Canonical metadata serialisation sorts unordered sets such as tags, handling
  labels and asset types, so restarting under a new Python process cannot
  change an unchanged corpus hash.
- Ticket documents are generation-scoped. An older vector can never be paired
  with document text or state written by a later generation.
- Starting the application recovers any persisted in-process rebuild left in
  `indexing` as `worker_interrupted`. A new rebuild can then start normally.
- Generation promotion is atomic. The candidate must still be `indexing`
  before the previous active generation is deactivated. A failed or stale
  candidate leaves the previous ready generation active.
- Promotion rejects duplicate, missing, unexpected or source-hash-mismatched
  document and vector identities before writing the candidate.
- The migration deliberately clears existing ticket documents and ticket
  embeddings because they are derived data whose old cross-generation pairing
  cannot be trusted. Product chunks and embeddings are preserved, but every old
  ready generation is invalidated until a complete rebuild succeeds.
- Local Compose runs Alembic as a one-shot service and will not start API writers
  unless the schema reaches head successfully.

## Security and privacy

- Retrieval provider tests require `SYSTEM_CONFIGURE`, CSRF validation and the
  existing provider-admission boundary.
- Provider errors remain reduced to safe messages. Keys, raw upstream responses
  and corpus text are never returned or logged.
- Provider JSON uses a total deadline and explicit byte limits. Encoded,
  oversized, malformed and non-numeric responses fail with fixed reasons.
- No external provider is activated, tested or sent corpus data automatically.
- Local cleanup is limited to the identified synthetic stress-test products and
  is verified before mutation.

## Acceptance criteria

1. The retrieval panel renders a live configuration summary, provider choices,
   provider-specific credential step, model choices, scoped connection result,
   apply action and index action with accessible labels and keyboard behaviour.
2. A mock draft test reports `mock` and `token-hash-v2`; a Gemini draft test
   reports `gemini_api` and `gemini-embedding-2` without first activating it.
3. Invalid provider, model, key and egress combinations fail closed without
   changing active configuration.
4. A successful test for one draft cannot authorise applying another draft.
5. Re-seeding the unchanged catalogue leaves product timestamps and the corpus
   version stable across application restarts.
6. Every generated demo object matches its declared size and hash. Demo PDFs
   can be parsed by the configured PDF reader.
7. After scoped cleanup and a mock rebuild, the live index becomes ready with
   current product and eligible request-vector counts. A second restart leaves
   it ready.
8. Backend and frontend tests cover the success, failure, stale-test,
   permission, egress, idempotency and asset-integrity paths.
9. Restart recovery unblocks an interrupted rebuild, failed promotion preserves
   the previous active generation, and rolling back to an older generation
   returns that generation's ticket document.

## Out of scope

- Automatically enabling Gemini because a key is present.
- Sending the local corpus to an external provider without an administrator's
  explicit activation and rebuild action.
- Treating unsupported binary formats as extractable text.
- Replacing PostgreSQL or pgvector with another retrieval store.

## Related decisions and guidance

- [Grounded search and embedding provenance](../adr/0034-grounded-search-and-embedding-provenance.md)
- [Search retrieval and duplicate assurance](search-retrieval-and-duplicate-assurance.md)
- [Search retrieval threat model](../threat-model/search-retrieval-and-duplicate-assurance.md)
- [Local demo dataset](local-demo-dataset.md)
