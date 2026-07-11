# Admin AI Provider, Model Selection and Store Date Search

## AI providers

Selectable providers (`services/ai_provider_catalog.py`): Gemini API
(primary, always listed first), OpenAI API, GCP Vertex AI (express-mode API
key), AWS Bedrock (long-term API key) and the offline mock. All providers
are key-based over plain HTTPS through one gateway
(`integrations/llm_gateway.py`); keys travel in headers, never in URLs, and
no vendor SDKs are used. Per-provider model allow-lists and defaults come
from settings (`available_*_models`) as a curated fallback.

The selectable model set is not frozen to those defaults. An administrator
can **refresh** a provider's list from its live API (OpenAI and Gemini
expose a listing endpoint over the same key; `integrations/llm_models.py`
filters to chat models) and can **add a model id by hand** for any provider,
so brand-new models are usable the day they ship even before, or without, a
listing. Discovered and hand-added ids are held per provider on top of the
curated defaults and persisted (they are not secrets); the effective list is
`curated + extras`.

One `AiModelService` instance serves the whole application, so the active
provider and model apply to every user at once.

## Admin API

All endpoints require `system:configure`; writes also require CSRF.

- `GET /api/v1/admin/ai-model` returns the active provider and model plus a
  `providers` array (name, label, allow-listed models, per-provider active
  model, whether a key is configured).
- `PUT /api/v1/admin/ai-model` with `{model, provider?}` switches a
  provider's selected model (default: the active provider). Unknown models
  return `422 model_not_available`; changes are audit logged
  (`ai_model_changed`).
- `PUT /api/v1/admin/ai-model/api-key` with `{apiKey, provider?}` stores a
  write-only runtime key for that provider (default `gemini_api`). Saving a
  key never switches the provider. Keys are held in memory only: never
  returned to clients, never persisted, gone on restart (audit:
  `ai_api_key_configured`).
- `PUT /api/v1/admin/ai-model/provider` with `{provider}` activates a
  provider for the whole application. Activation requires a configured key
  (`422 provider_not_configured` otherwise, `422 provider_not_available`
  for unknown names) and is audit logged (`ai_provider_changed`). Every
  active administrator receives an in-app notification naming who switched,
  to what, and that the change affects all users immediately; the admin UI
  shows the same warning and requires an explicit confirmation.
- `POST /api/v1/admin/ai-model/test` with `{provider?}` sends one tiny test
  prompt through the provider and reports `{ok, provider, model, message}`
  without changing any state, so admins can prove a key works before
  activating. Missing keys and unreachable providers report `ok: false`
  rather than erroring.
- `POST /api/v1/admin/ai-model/refresh` with `{provider}` reloads that
  provider's models from its live API and appends any new ids to the
  selectable list (audit: `ai_models_refreshed`). Requires a configured key
  (`409 provider_not_configured`); providers without a usable listing
  endpoint (Vertex AI, Bedrock) return `422 refresh_not_supported`.
- `POST /api/v1/admin/ai-model/custom-model` with `{provider, model}` adds a
  model id by hand (validated `^[A-Za-z0-9._:\-/]+$`) and selects it for that
  provider, covering brand-new models and providers without live listing
  (audit: `ai_custom_model_added`).

## Environment configuration

`COEUS_LLM_PROVIDER` plus the matching key env var
(`COEUS_GEMINI_API_KEY`, `COEUS_OPENAI_API_KEY`, `COEUS_VERTEX_API_KEY`,
`COEUS_BEDROCK_API_KEY`; Bedrock also reads `COEUS_BEDROCK_REGION`).
An env key alone never switches the provider. Hosted environments refuse to
boot with a non-mock provider and no key. Locally the provider remains
`mock` unless explicitly enabled. Search embeddings are a separate switch
(`COEUS_EMBEDDING_PROVIDER`) and always use the Gemini key.

## Store date search

- `GET /api/v1/store/products` accepts optional `dateFrom` and `dateTo`
  ISO dates (`YYYY-MM-DD`, validated by pattern).
- A product matches when its coverage period overlaps the requested range.
  Products without a recorded period do not match date-filtered searches.
- Seed products carry synthetic coverage periods so local date search is
  demonstrable. ACG and classification checks continue to run before any
  filtering.
