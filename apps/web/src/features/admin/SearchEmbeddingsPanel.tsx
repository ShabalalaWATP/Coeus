import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, KeyRound, PlugZap, RefreshCw, Save } from "lucide-react";
import { useEffect, useState } from "react";

import {
  configureSearchEmbeddingKey,
  configureSearchEmbeddings,
  getSearchEmbeddingState,
  reindexSearchEmbeddings,
  testSearchEmbeddings,
} from "../../lib/api-client/admin";

const QUERY_KEY = ["admin-search-embeddings"] as const;
const MODEL_OPTIONS: Record<string, string[]> = {
  gemini_api: ["gemini-embedding-2"],
  mock: ["token-hash-v2"],
};

export function SearchEmbeddingsPanel({ csrfToken }: { csrfToken: string }) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: getSearchEmbeddingState,
    refetchInterval: (current) => (current.state.data?.indexStatus === "indexing" ? 2_000 : false),
  });
  const [provider, setProvider] = useState("mock");
  const [model, setModel] = useState("token-hash-v2");
  const [apiKey, setApiKey] = useState("");
  const [egressConfirmed, setEgressConfirmed] = useState(false);

  useEffect(() => {
    if (query.data) {
      setProvider(query.data.provider);
      setModel(query.data.model);
    }
  }, [query.data]);

  const updateCache = (state: Awaited<ReturnType<typeof getSearchEmbeddingState>>) =>
    queryClient.setQueryData(QUERY_KEY, state);
  const keyMutation = useMutation({
    mutationFn: () => configureSearchEmbeddingKey(apiKey.trim(), csrfToken),
    onSuccess: (state) => {
      setApiKey("");
      updateCache(state);
    },
  });
  const configurationMutation = useMutation({
    mutationFn: () => configureSearchEmbeddings(provider, model, egressConfirmed, csrfToken),
    onSuccess: updateCache,
  });
  const testMutation = useMutation({ mutationFn: () => testSearchEmbeddings(csrfToken) });
  const reindexMutation = useMutation({
    mutationFn: () => reindexSearchEmbeddings(csrfToken),
    onSuccess: updateCache,
  });
  const state = query.data;
  const models = MODEL_OPTIONS[provider] ?? state?.availableModels ?? [];
  const providerReady = provider === "mock" || Boolean(state?.apiKeyConfigured);

  return (
    <section className="surface search-admin" aria-labelledby="search-embedding-title">
      <header className="search-admin__heading">
        <span className="chat-panel__icon">
          <Database aria-hidden="true" size={20} />
        </span>
        <div>
          <span className="eyebrow">Independent retrieval API</span>
          <h2 id="search-embedding-title">Search &amp; embeddings</h2>
          <p>
            Configure grounded Intelligence Store search separately from Istari chat and Realtime
            voice.
          </p>
        </div>
      </header>

      {query.isLoading ? <p role="status">Loading search settings…</p> : null}
      {query.isError ? (
        <p className="workspace-alert" role="alert">
          Search settings are unavailable.
        </p>
      ) : null}
      {state ? (
        <div className="search-admin__body">
          <div className="search-admin__facts" aria-label="Search index status">
            <Status label="Provider" value={state.provider} />
            <Status label="Model" value={state.model} />
            <Status label="Vector size" value={`${state.dimensions} dimensions`} />
            <Status label="Index" value={state.indexStatus} />
            <Status label="Products" value={String(state.productCount)} />
            <Status label="Passages" value={String(state.chunkCount)} />
            <Status label="Active requests" value={String(state.ticketCount)} />
            <Status label="Asset warnings" value={String(state.failedAssetCount)} />
            <Status label="Generation" value={String(state.indexGeneration)} />
            <Status label="Corpus" value={state.corpusVersion.slice(0, 12)} />
          </div>

          <div className="ai-step">
            <span className="ai-step__label">
              <KeyRound aria-hidden="true" size={14} /> Dedicated Gemini search key
            </span>
            <div className="ai-key-row">
              <label htmlFor="search-api-key">
                <span className="ai-field-label">Embedding API key</span>
                <input
                  autoComplete="off"
                  id="search-api-key"
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder={state.apiKeyConfigured ? "Search key configured" : "Paste key"}
                  type="password"
                  value={apiKey}
                />
              </label>
              <button
                className="ai-btn-secondary"
                disabled={keyMutation.isPending || apiKey.trim().length < 10}
                onClick={() => keyMutation.mutate()}
                type="button"
              >
                <Save aria-hidden="true" size={16} />
                {keyMutation.isPending ? "Saving…" : "Save search key"}
              </button>
            </div>
            <small className="field-hint">
              Encrypted at rest and never returned. It is not shared with text chat or voice.
            </small>
          </div>

          <form
            className="search-admin__configuration"
            onSubmit={(event) => {
              event.preventDefault();
              configurationMutation.mutate();
            }}
          >
            <label htmlFor="search-provider">Embedding provider</label>
            <select
              id="search-provider"
              onChange={(event) => {
                const next = event.target.value;
                setProvider(next);
                setModel(MODEL_OPTIONS[next]?.[0] ?? "");
                setEgressConfirmed(false);
              }}
              value={provider}
            >
              {state.availableProviders.map((item) => (
                <option key={item} value={item}>
                  {item === "gemini_api" ? "Gemini API" : "Offline mock"}
                </option>
              ))}
            </select>
            <label htmlFor="search-model">Embedding model</label>
            <select
              id="search-model"
              onChange={(event) => setModel(event.target.value)}
              value={model}
            >
              {models.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
            {provider === "gemini_api" ? (
              <label className="search-admin__egress">
                <input
                  checked={egressConfirmed}
                  onChange={(event) => setEgressConfirmed(event.target.checked)}
                  type="checkbox"
                />
                I confirm that synthetic Store text may be sent to the Gemini Embeddings API.
              </label>
            ) : null}
            <button
              disabled={
                configurationMutation.isPending ||
                !providerReady ||
                (provider === "gemini_api" && !egressConfirmed)
              }
              type="submit"
            >
              <Save aria-hidden="true" size={16} /> Save retrieval configuration
            </button>
          </form>

          <div className="search-admin__actions">
            <button
              className="ai-btn-secondary"
              disabled={testMutation.isPending || !providerReady}
              onClick={() => testMutation.mutate()}
              type="button"
            >
              <PlugZap aria-hidden="true" size={16} />
              {testMutation.isPending ? "Testing…" : "Test connection"}
            </button>
            <button
              disabled={reindexMutation.isPending || state.indexStatus === "indexing"}
              onClick={() => reindexMutation.mutate()}
              type="button"
            >
              <RefreshCw aria-hidden="true" size={16} />
              {state.indexStatus === "indexing" ? "Re-indexing…" : "Rebuild search index"}
            </button>
          </div>
          <MutationMessage
            error={keyMutation.isError || configurationMutation.isError || reindexMutation.isError}
            testMessage={testMutation.data?.message}
          />
          {state.degradedReason ? (
            <p className="workspace-alert" role="alert">
              Retrieval is degraded: {state.degradedReason.replaceAll("_", " ")}.
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function Status({ label, value }: { label: string; value: string }) {
  return (
    <span>
      <small>{label}</small>
      <strong>{value}</strong>
    </span>
  );
}

function MutationMessage({ error, testMessage }: { error: boolean; testMessage?: string }) {
  if (error)
    return (
      <p className="field-hint" role="alert">
        Search settings could not be updated.
      </p>
    );
  if (testMessage)
    return (
      <p className="search-admin__success" role="status">
        {testMessage}
      </p>
    );
  return null;
}
