import { Check, KeyRound, PlugZap, Save, ShieldCheck } from "lucide-react";

import { searchModelLabel, searchProviderLabel } from "./searchEmbeddingLabels";
import { searchEmbeddingPresentation } from "./searchEmbeddingPresentation";
import { type SearchEmbeddingsController } from "./useSearchEmbeddingsPanelController";

export function SearchConfigurationSummary({
  state,
}: {
  state: NonNullable<SearchEmbeddingsController["state"]>;
}) {
  const presentation = searchEmbeddingPresentation(state);
  return (
    <div
      aria-live="polite"
      className={`search-admin__overview search-admin__overview--${
        presentation.needsAttention ? "attention" : presentation.isUpdating ? "updating" : "ready"
      }`}
      role="status"
    >
      <span aria-hidden="true" className="search-admin__overview-dot" />
      <div>
        <small>Automatic search</small>
        <strong>{presentation.title}</strong>
        <p>{presentation.description}</p>
      </div>
    </div>
  );
}

export function SearchEmbeddingConfiguration({
  controller,
}: {
  controller: SearchEmbeddingsController;
}) {
  const {
    state,
    provider,
    model,
    models,
    apiKey,
    egressConfirmed,
    actionPending,
    providerReady,
    egressReady,
    configurationChanged,
    draftTested,
    selectProvider,
    selectModel,
    updateApiKey,
    setEgressConfirmed,
    keyMutation,
    testMutation,
    configurationMutation,
  } = controller;
  if (!state) return null;
  const canTest = providerReady && egressReady && Boolean(model) && !actionPending;
  const canApply = canTest && configurationChanged && draftTested;

  return (
    <details className="search-admin__configuration">
      <summary>
        <span>Change search service</span>
        <small>Advanced settings for Gemini, local search and API keys</small>
      </summary>
      <section aria-labelledby="search-provider-heading" className="search-admin__provider">
        <div>
          <h3 id="search-provider-heading">Search service settings</h3>
          <p className="ai-hint">
            Choose and test the service that prepares Intelligence Store search.
          </p>
        </div>
        <div aria-label="Embedding providers" className="ai-provider-row" role="group">
          {[...state.availableProviders]
            .sort((left, right) => Number(left === "mock") - Number(right === "mock"))
            .map((name) => {
              const isActive = name === state.provider;
              const isChosen = name === provider;
              const keyReady = name === "mock" || state.apiKeyConfigured;
              return (
                <button
                  aria-pressed={isChosen}
                  className={`ai-provider-tab${isChosen ? " ai-provider-tab--chosen" : ""}`}
                  disabled={actionPending}
                  key={name}
                  onClick={() => selectProvider(name)}
                  type="button"
                >
                  {searchProviderLabel(name)}
                  <span
                    className={`ai-provider-tab__status ai-provider-tab__status--${isActive ? "live" : name === "mock" ? "local" : keyReady ? "ready" : "empty"}`}
                  >
                    {isActive
                      ? "Live"
                      : name === "mock"
                        ? "Local"
                        : keyReady
                          ? "Key set"
                          : "No key"}
                  </span>
                </button>
              );
            })}
        </div>

        <div className="ai-provider-detail">
          {provider === "gemini_api" ? (
            <div className="ai-step">
              <span className="ai-step__label">
                <KeyRound aria-hidden="true" size={14} /> Step 1 · Dedicated search key
              </span>
              <form
                className="ai-key-row"
                onSubmit={(event) => {
                  event.preventDefault();
                  keyMutation.mutate();
                }}
              >
                <label htmlFor="search-api-key">
                  <span className="ai-field-label">Embedding API key</span>
                  <input
                    autoComplete="off"
                    disabled={actionPending}
                    id="search-api-key"
                    onChange={(event) => updateApiKey(event.target.value)}
                    placeholder={state.apiKeyConfigured ? "Search key configured" : "Paste key"}
                    type="password"
                    value={apiKey}
                  />
                </label>
                <button
                  className="ai-btn-secondary"
                  disabled={actionPending || apiKey.trim().length < 10}
                  type="submit"
                >
                  <Save aria-hidden="true" size={16} />{" "}
                  {keyMutation.isPending ? "Saving…" : "Save search key"}
                </button>
              </form>
              <p className="ai-hint">
                Encrypted at rest and never returned. It is not shared with text chat or voice.
              </p>
              <p
                className={`admin-key-state ${state.apiKeyConfigured ? "admin-key-state--saved" : ""}`}
              >
                {state.apiKeyConfigured
                  ? "A dedicated Gemini embeddings key is saved. Test it before activation."
                  : "No dedicated Gemini embeddings key is saved."}
              </p>
            </div>
          ) : (
            <p className="ai-hint">
              Runs locally with deterministic token hashing. No key or external network access is
              required.
            </p>
          )}

          <div className="ai-step">
            <span className="ai-step__label">
              <ShieldCheck aria-hidden="true" size={14} />{" "}
              {provider === "gemini_api" ? "Step 2" : "Step 1"} · Embedding model
            </span>
            <div
              aria-label="Available embedding models"
              className="ai-model-grid"
              role="radiogroup"
            >
              {models.map((name) => {
                const chosen = name === model;
                const active = provider === state.provider && name === state.model;
                return (
                  <label
                    className={`ai-model-card${chosen ? " ai-model-card--chosen" : ""}`}
                    key={name}
                  >
                    <input
                      checked={chosen}
                      disabled={actionPending}
                      name="search-embedding-model"
                      onChange={() => selectModel(name)}
                      type="radio"
                      value={name}
                    />
                    <span className="ai-model-card__header">
                      <strong>{searchModelLabel(name)}</strong>
                      <span className="ai-model-tier">1,536d</span>
                    </span>
                    <span className="ai-model-card__description">
                      {provider === "mock"
                        ? "Private, deterministic retrieval that works without a network connection."
                        : "Quality-first external embeddings for the Intelligence Store."}
                    </span>
                    {active ? (
                      <span className="ai-model-card__active">
                        <Check aria-hidden="true" size={13} /> Active
                      </span>
                    ) : null}
                  </label>
                );
              })}
            </div>
          </div>

          {provider === "gemini_api" ? (
            <label className="search-admin__egress">
              <input
                checked={egressConfirmed}
                disabled={actionPending}
                onChange={(event) => setEgressConfirmed(event.target.checked)}
                type="checkbox"
              />
              I confirm that the synthetic connection-test phrase may be sent to Gemini and that
              applying this provider enables external embeddings when the index is rebuilt.
            </label>
          ) : null}

          <div className="ai-actions">
            <button
              className="ai-btn-secondary"
              disabled={!canTest}
              onClick={() => testMutation.mutate()}
              type="button"
            >
              <PlugZap aria-hidden="true" size={16} />{" "}
              {testMutation.isPending ? "Testing…" : `Test ${searchProviderLabel(provider)}`}
            </button>
            <button
              className="ai-btn-primary"
              disabled={!canApply}
              onClick={() => configurationMutation.mutate()}
              type="button"
            >
              <Save aria-hidden="true" size={16} />{" "}
              {configurationMutation.isPending ? "Applying…" : "Apply retrieval configuration"}
            </button>
          </div>
          {!configurationChanged ? (
            <small className="field-hint">This is the live retrieval configuration.</small>
          ) : null}
          {configurationChanged && !draftTested ? (
            <small className="field-hint">Test this provider and model before applying it.</small>
          ) : null}
          <MutationMessage controller={controller} />
        </div>
      </section>
    </details>
  );
}

function MutationMessage({ controller }: { controller: SearchEmbeddingsController }) {
  const { keyMutation, configurationMutation, testMutation } = controller;
  if (keyMutation.isError || configurationMutation.isError)
    return (
      <p className="field-hint" role="alert">
        Search settings could not be updated.
      </p>
    );
  if (testMutation.isError)
    return (
      <p className="field-hint" role="alert">
        The selected search connection could not be tested.
      </p>
    );
  if (!testMutation.data) return null;
  return (
    <p
      className={`ai-test-result ai-test-result--${testMutation.data.ok ? "ok" : "fail"}`}
      role={testMutation.data.ok ? "status" : "alert"}
    >
      {testMutation.data.ok ? "Connection OK" : "Connection failed"}:{" "}
      {searchProviderLabel(testMutation.data.provider)} ·{" "}
      {searchModelLabel(testMutation.data.model)}. {testMutation.data.message}
      {!testMutation.data.ok && testMutation.data.provider === "gemini_api"
        ? " Replace the saved Gemini key or select another supported model, then test again."
        : null}
    </p>
  );
}
