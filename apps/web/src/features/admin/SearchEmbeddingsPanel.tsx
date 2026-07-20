import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, KeyRound, PlugZap, RefreshCw, Save } from "lucide-react";
import { useEffect, useState } from "react";

import { AdminDisclosureSummary } from "./AdminDisclosureSummary";
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
const providerLabels: Record<string, string> = {
  gemini_api: "Gemini API",
  mock: "Offline mock",
};
export function SearchEmbeddingsPanel({
  csrfToken,
  initiallyOpen = true,
}: {
  csrfToken: string;
  initiallyOpen?: boolean;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(initiallyOpen);
  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: getSearchEmbeddingState,
    refetchInterval: (current) => (current.state.data?.indexStatus === "indexing" ? 2_000 : false),
  });
  const [provider, setProvider] = useState("mock");
  const [model, setModel] = useState("token-hash-v2");
  const [apiKey, setApiKey] = useState("");
  const [egressConfirmed, setEgressConfirmed] = useState(false);
  const [testedConfiguration, setTestedConfiguration] = useState<string | null>(null);
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
    onMutate: () => clearTest(),
    onSuccess: (state) => {
      setApiKey("");
      updateCache(state);
    },
  });
  const configurationMutation = useMutation({
    mutationFn: () => configureSearchEmbeddings(provider, model, egressConfirmed, csrfToken),
    onMutate: () => clearTest(),
    onSuccess: updateCache,
  });
  const testMutation = useMutation({
    mutationFn: () => testSearchEmbeddings(csrfToken),
    onSuccess: (result) =>
      setTestedConfiguration(result.ok ? `${result.provider}:${result.model}` : null),
  });
  const reindexMutation = useMutation({
    mutationFn: () => reindexSearchEmbeddings(csrfToken),
    onSuccess: updateCache,
  });
  const state = query.data;
  const models = MODEL_OPTIONS[provider] ?? state?.availableModels ?? [];
  const providerReady = provider === "mock" || Boolean(state?.apiKeyConfigured);
  const savedKey = Boolean(state?.apiKeyConfigured);
  const savedDraft =
    Boolean(state) &&
    provider === state?.provider &&
    model === state?.model &&
    apiKey.trim() === "";
  const testedSavedConfiguration =
    Boolean(state) &&
    savedDraft &&
    testMutation.data?.ok === true &&
    testedConfiguration === `${state?.provider}:${state?.model}`;
  const actionPending =
    keyMutation.isPending ||
    configurationMutation.isPending ||
    testMutation.isPending ||
    reindexMutation.isPending;

  function clearTest() {
    testMutation.reset();
    setTestedConfiguration(null);
  }
  return (
    <details
      className="surface admin-disclosure search-admin"
      onToggle={(event) => setOpen(event.currentTarget.open)}
      open={open}
    >
      <AdminDisclosureSummary
        description="Configure Intelligence Store retrieval independently from chat and voice."
        eyebrow="Independent retrieval API"
        icon={Database}
        statuses={[
          {
            label: state
              ? `${providerLabels[state.provider] ?? state.provider} active`
              : "Loading provider",
            tone: state ? "active" : "neutral",
          },
          state ? { label: state.model } : { label: "Loading model" },
          state?.provider === "mock"
            ? { label: "No key required", tone: "active" }
            : savedKey
              ? { label: "Key saved", tone: "active" }
              : { label: "No key saved", tone: "attention" },
          state
            ? {
                label: `Index ${state.indexStatus}`,
                tone: state.indexStatus === "ready" ? "active" : "attention",
              }
            : { label: "Checking index" },
          state
            ? {
                label: `Evaluation ${state.evaluationStatus}`,
                tone: state.definitiveNoMatchEnabled ? "active" : "attention",
              }
            : { label: "Checking evaluation" },
          ...(testedSavedConfiguration
            ? [{ label: `Tested ${state?.model ?? "embeddings"}`, tone: "active" as const }]
            : []),
        ]}
        title="Search & embeddings"
        titleId="search-embedding-title"
      />
      <div className="admin-disclosure__body">
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
              <Status label="Search release" value={state.releaseId} />
            </div>
            {!state.definitiveNoMatchEnabled ? (
              <p className="workspace-alert" role="status">
                This provider/model has not passed the approved retrieval evaluation. Results may be
                offered for review, but Istari will not claim a definitive no-match.
              </p>
            ) : null}

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
                    disabled={actionPending}
                    onChange={(event) => {
                      setApiKey(event.target.value);
                      clearTest();
                    }}
                    placeholder={state.apiKeyConfigured ? "Search key configured" : "Paste key"}
                    type="password"
                    value={apiKey}
                  />
                </label>
                <button
                  className="ai-btn-secondary"
                  disabled={actionPending || apiKey.trim().length < 10}
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
              <p className={`admin-key-state ${savedKey ? "admin-key-state--saved" : ""}`}>
                {savedKey
                  ? "A dedicated Gemini embeddings key is saved. Test it below to verify access."
                  : "No dedicated Gemini embeddings key is saved."}
              </p>
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
                disabled={actionPending}
                onChange={(event) => {
                  const next = event.target.value;
                  setProvider(next);
                  setModel(MODEL_OPTIONS[next]?.[0] ?? "");
                  setEgressConfirmed(false);
                  clearTest();
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
                disabled={actionPending}
                onChange={(event) => {
                  setModel(event.target.value);
                  clearTest();
                }}
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
                    disabled={actionPending}
                    onChange={(event) => setEgressConfirmed(event.target.checked)}
                    type="checkbox"
                  />
                  I confirm that synthetic Store text may be sent to the Gemini Embeddings API.
                </label>
              ) : null}
              <button
                disabled={
                  actionPending || !providerReady || (provider === "gemini_api" && !egressConfirmed)
                }
                type="submit"
              >
                <Save aria-hidden="true" size={16} /> Save retrieval configuration
              </button>
            </form>

            <div className="search-admin__actions">
              <button
                className="ai-btn-secondary"
                disabled={actionPending || !providerReady || !savedDraft}
                onClick={() => testMutation.mutate()}
                type="button"
              >
                <PlugZap aria-hidden="true" size={16} />
                {testMutation.isPending ? "Testing…" : "Test connection"}
              </button>
              <button
                disabled={actionPending || state.indexStatus === "indexing"}
                onClick={() => reindexMutation.mutate()}
                type="button"
              >
                <RefreshCw aria-hidden="true" size={16} />
                {state.indexStatus === "indexing" ? "Re-indexing…" : "Rebuild search index"}
              </button>
            </div>
            {!savedDraft ? (
              <small className="field-hint">Save or clear draft changes before testing.</small>
            ) : null}
            <MutationMessage
              error={
                keyMutation.isError || configurationMutation.isError || reindexMutation.isError
              }
              testError={testMutation.isError}
              testResult={testMutation.data}
            />
            {state.degradedReason ? (
              <p className="workspace-alert" role="alert">
                Retrieval is degraded: {state.degradedReason.replaceAll("_", " ")}.
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </details>
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

function MutationMessage({
  error,
  testError,
  testResult,
}: {
  error: boolean;
  testError: boolean;
  testResult?: { message: string; ok: boolean };
}) {
  if (error)
    return (
      <p className="field-hint" role="alert">
        Search settings could not be updated.
      </p>
    );
  if (testError)
    return (
      <p className="field-hint" role="alert">
        The search connection test could not be run.
      </p>
    );
  if (testResult)
    return (
      <p
        className={`ai-test-result ai-test-result--${testResult.ok ? "ok" : "fail"}`}
        role={testResult.ok ? "status" : "alert"}
      >
        {testResult.ok ? "Connection OK: " : "Connection failed: "}
        {testResult.message}
      </p>
    );
  return null;
}
