# Admin AI Model Selection and Store Date Search

## AI model selection

- `GET /api/v1/admin/ai-model` returns the active LLM provider, the active
  Gemini model and the allowed model list (`available_gemini_models`
  setting). Requires `system:configure`.
- `PUT /api/v1/admin/ai-model` with `{model}` switches the active model.
  Requires `system:configure` plus CSRF; unknown models return
  `422 model_not_available`; changes are audit logged with the previous and
  new model.
- Locally the provider remains `mock`; the selection records which Gemini
  model deployed environments call through Vertex AI.

## Store date search

- `GET /api/v1/store/products` accepts optional `dateFrom` and `dateTo`
  ISO dates (`YYYY-MM-DD`, validated by pattern).
- A product matches when its coverage period overlaps the requested range.
  Products without a recorded period do not match date-filtered searches.
- Seed products carry synthetic coverage periods so local date search is
  demonstrable. ACG and classification checks continue to run before any
  filtering.
