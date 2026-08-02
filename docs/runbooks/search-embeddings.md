# Search Embeddings Runbook

Istari keeps retrieval independent from text chat and Realtime voice. It also
has two deliberately separate Store search projections.

## Compatibility Store projection

The compatibility Store search combines PostgreSQL full text with a
384-dimension pgvector leg. `COEUS_EMBEDDING_PROVIDER` defaults to deterministic
offline `mock`. For a real offline model, set the provider to `local` and
install the optional dependency:

```powershell
uv sync --project apps/api --extra embeddings
```

`BAAI/bge-small-en-v1.5` loads from `COEUS_EMBEDDING_MODEL_PATH`, which defaults
to `.local-data/embedding-models`. Download it there in advance for a fully
offline machine. `gemini_api` uses the configured Gemini key. A key never
switches the provider by itself. Provider failure degrades this projection to
its lexical leg rather than failing Store search.

Embeddings are written when products are created, updated or ingested at QC.
Backfill older products with the bounded, idempotent tool:

```powershell
uv run --project apps/api python -m coeus.tools.backfill_embeddings
```

## Grounded generation index

The 1,536-dimension grounded index is managed in **Admin > Search & embeddings**:

The main status uses three operational states:

- **Ready**: search is current and available.
- **Updating automatically**: a change is queued or being prepared. No action
  is required, the page checks for completion automatically.
- **Needs attention**: the automatic update failed. Use **Try automatic update
  again** after correcting the stated connection or key problem.

To change the service, open **Change search service**, save its dedicated key if
required, select the model, confirm external egress where required, test the
exact draft and apply it. Applying queues the compatible search-library update.
There is no routine manual rebuild step.

The connection probe sends only a fixed synthetic phrase. Applying selects the
query embedding space but does not send corpus text. Rebuilding is the action
that embeds eligible Store and request text. Changing the draft provider, model
or saved key invalidates the previous test. Provider responses use total
deadlines, reject encoded or oversized bodies and reduce malformed values to a
fixed unavailable reason without logging upstream content.

The interface presents internal `stale` and `indexing` states as **Updating
automatically**. Internally, stale means canonical indexed inputs changed after
the active generation. Failed means the latest build failed or a ready
configuration has no active generation. An interrupted process-local build is
marked `worker_interrupted` at restart and may be retried. File warnings report
extraction outcomes and do not mean the embedding connection failed.

Compose upgrades the database before starting the API. The generation-integrity
migration deliberately clears derived request documents and vectors, and marks
older ready generations failed so they cannot be reused without matching request
data. Startup automatically queues a replacement generation after that
migration. An operator uses **Try automatic update again** only if the queued
attempt fails. Each later promotion verifies unique, one-to-one chunk and
request identities plus matching source hashes before any candidate can become
active. Generation, corpus, release and vector details are available under the
collapsed **Technical details** section for diagnosis.

See the [user workflow](../USER_GUIDE.md#search-embeddings),
[retrieval architecture](../architecture/DATA_SEARCH_AND_AI.md#4-two-index-retrieval-and-assurance)
and [security model](../threat-model/search-retrieval-and-duplicate-assurance.md).
