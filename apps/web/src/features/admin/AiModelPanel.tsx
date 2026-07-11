import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, Check, KeyRound, PlugZap, Save, ShieldAlert, Sparkles } from "lucide-react";
import { useState } from "react";

import { AiModelGrid } from "./AiModelGrid";
import { errorText, providerStatus, type ModelNote } from "./ai-model-panel-utils";
import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  addCustomAiModel,
  configureAiApiKey,
  getAiModelState,
  refreshAiModels,
  selectAiModel,
  selectAiProvider,
  testAiConnection,
  type AiConnectionTest,
  type AiModelState,
} from "../../lib/api-client/admin";
import { useActionError } from "../../lib/mutations/action-error";

type AiModelPanelProps = {
  csrfToken: string;
};

export function AiModelPanel({ csrfToken }: AiModelPanelProps) {
  const queryClient = useQueryClient();
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [testResult, setTestResult] = useState<AiConnectionTest | null>(null);
  const [modelNote, setModelNote] = useState<ModelNote | null>(null);
  const [confirmingActivation, setConfirmingActivation] = useState(false);
  const { actionError, clearActionError, failActionWith } = useActionError();
  const stateQuery = useQuery({ queryKey: ["ai-model"], queryFn: getAiModelState });
  const state = stateQuery.data;
  const providerName = selectedProvider ?? state?.provider ?? "gemini_api";
  const provider = state?.providers.find((entry) => entry.name === providerName);
  const liveProvider = state?.providers.find((entry) => entry.name === state.provider);
  const applyState = (next: AiModelState) => queryClient.setQueryData(["ai-model"], next);
  const modelMutation = useMutation({
    mutationFn: (model: string) => selectAiModel(model, providerName, csrfToken),
    onError: failActionWith("The model could not be changed. Refresh and try again."),
    onMutate: clearActionError,
    onSuccess: (next: AiModelState) => {
      setSelectedModel(null);
      applyState(next);
    },
  });
  const keyMutation = useMutation({
    mutationFn: (key: string) => configureAiApiKey(key, providerName, csrfToken),
    onError: failActionWith("The API key could not be saved. Check the key and try again."),
    onMutate: clearActionError,
    onSuccess: (next: AiModelState) => {
      setApiKey("");
      applyState(next);
    },
  });
  const testMutation = useMutation({
    mutationFn: () => testAiConnection(providerName, csrfToken),
    onError: failActionWith("The connection test could not be run."),
    onMutate: () => {
      clearActionError();
      setTestResult(null);
    },
    onSuccess: setTestResult,
  });
  const activateMutation = useMutation({
    mutationFn: () => selectAiProvider(providerName, csrfToken),
    onError: failActionWith("The provider could not be activated."),
    onMutate: clearActionError,
    onSuccess: (next: AiModelState) => {
      setConfirmingActivation(false);
      applyState(next);
    },
  });
  const refreshMutation = useMutation({
    mutationFn: () => refreshAiModels(providerName, csrfToken),
    onMutate: () => {
      clearActionError();
      setModelNote(null);
    },
    onError: (error) =>
      setModelNote({ tone: "fail", text: errorText(error, "Could not refresh models.") }),
    onSuccess: (next: AiModelState) => {
      applyState(next);
      const entry = next.providers.find((item) => item.name === providerName);
      setModelNote({
        tone: "ok",
        text: `${entry?.models.length ?? 0} models available for ${entry?.label ?? providerName}.`,
      });
    },
  });
  const customMutation = useMutation({
    mutationFn: (model: string) => addCustomAiModel(providerName, model, csrfToken),
    onMutate: () => {
      clearActionError();
      setModelNote(null);
    },
    onError: (error) =>
      setModelNote({ tone: "fail", text: errorText(error, "That model id could not be added.") }),
    onSuccess: (next: AiModelState, model: string) => {
      applyState(next);
      setSelectedModel(null);
      setModelNote({ tone: "ok", text: `Added ${model} and selected it.` });
    },
  });
  const pickProvider = (name: string) => {
    setSelectedProvider(name);
    setSelectedModel(null);
    setApiKey("");
    setTestResult(null);
    setModelNote(null);
    setConfirmingActivation(false);
    clearActionError();
  };
  const activeChoice = selectedModel ?? provider?.activeModel ?? "";
  const isLive = provider?.name === state?.provider;
  const isMock = provider?.name === "mock";

  return (
    <section className="surface ai-model-panel" aria-labelledby="ai-model-title">
      <div className="section-heading access-heading">
        <BrainCircuit aria-hidden="true" size={20} />
        <div>
          <h2 id="ai-model-title">AI provider and model</h2>
          <p>
            Gemini API is the primary provider; OpenAI, GCP Vertex AI and AWS Bedrock are optional
            alternatives. Refresh the model list from a provider or add a new model id by hand to
            stay current. Search embeddings are configured separately.
          </p>
        </div>
      </div>
      {stateQuery.isError ? <ErrorState onRetry={() => void stateQuery.refetch()} /> : null}
      {stateQuery.isLoading ? <LoadingState label="Loading model configuration" /> : null}
      {state && provider ? (
        <div className="ai-model-body">
          <div className="ai-live" role="group" aria-label="Live AI configuration">
            <div className="ai-live__headline">
              <span className="ai-live__dot" aria-hidden="true" />
              <div>
                <span className="ai-live__eyebrow">Live for every user</span>
                <strong>
                  {liveProvider?.label ?? state.provider}
                  <span className="ai-live__model"> · {state.activeModel}</span>
                </strong>
              </div>
            </div>
            <dl className="ai-live__stats">
              <div>
                <dt>Embeddings</dt>
                <dd>{state.embeddingProvider}</dd>
              </div>
              <div>
                <dt>Products embedded</dt>
                <dd>{state.embeddedProductCount}</dd>
              </div>
              {state.changedBy ? (
                <div>
                  <dt>Last changed</dt>
                  <dd>
                    {state.changedBy}
                    {state.changedAt
                      ? ` · ${new Date(state.changedAt).toLocaleString("en-GB")}`
                      : ""}
                  </dd>
                </div>
              ) : null}
            </dl>
          </div>

          <div className="ai-provider-row" role="tablist" aria-label="Providers">
            {state.providers.map((entry) => {
              const status = providerStatus(entry, state.provider);
              const chosen = entry.name === providerName;
              return (
                <button
                  aria-selected={chosen}
                  className={`ai-provider-tab${chosen ? " ai-provider-tab--chosen" : ""}`}
                  key={entry.name}
                  onClick={() => pickProvider(entry.name)}
                  role="tab"
                  type="button"
                >
                  <span className="ai-provider-tab__name">{entry.label}</span>
                  <span
                    className={`ai-provider-tab__status ai-provider-tab__status--${status.tone}`}
                  >
                    {status.tone === "live" ? <Check aria-hidden="true" size={12} /> : null}
                    {status.label}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="ai-provider-detail">
            {isMock ? (
              <p className="ai-hint">
                The mock provider answers locally with deterministic replies and needs no key. Use
                it for offline demos and tests.
              </p>
            ) : (
              <>
                <div className="ai-step">
                  <span className="ai-step__label">
                    <KeyRound aria-hidden="true" size={14} />
                    Step 1 — API key
                  </span>
                  <div className="ai-key-row">
                    <label>
                      <span className="ai-field-label">API key</span>
                      <input
                        autoComplete="off"
                        onChange={(event) => setApiKey(event.target.value)}
                        placeholder={
                          provider.apiKeyConfigured ? "API key configured" : "Paste API key"
                        }
                        type="password"
                        value={apiKey}
                      />
                    </label>
                    <button
                      className="ai-btn-secondary"
                      disabled={keyMutation.isPending || apiKey.trim().length < 10}
                      onClick={() => keyMutation.mutate(apiKey.trim())}
                      type="button"
                    >
                      <Save aria-hidden="true" size={16} />
                      Save key
                    </button>
                  </div>
                </div>
                <div className="ai-step">
                  <span className="ai-step__label">
                    <Sparkles aria-hidden="true" size={14} />
                    Step 2 — Model
                  </span>
                  <AiModelGrid
                    activeChoice={activeChoice}
                    addingCustom={customMutation.isPending}
                    onAddCustom={(model) => customMutation.mutate(model)}
                    onApply={() => modelMutation.mutate(activeChoice)}
                    onChoose={setSelectedModel}
                    onRefresh={() => refreshMutation.mutate()}
                    pending={modelMutation.isPending}
                    provider={provider}
                    refreshing={refreshMutation.isPending}
                  />
                  {modelNote ? (
                    <p className={`ai-model-note ai-model-note--${modelNote.tone}`} role="status">
                      {modelNote.text}
                    </p>
                  ) : null}
                </div>
              </>
            )}
            <div className="ai-actions">
              <button
                className="ai-btn-secondary"
                disabled={testMutation.isPending}
                onClick={() => testMutation.mutate()}
                type="button"
              >
                <PlugZap aria-hidden="true" size={16} />
                {testMutation.isPending ? "Testing connection" : "Test connection"}
              </button>
              {isLive ? (
                <span className="ai-live-tag">
                  <Check aria-hidden="true" size={14} />
                  This provider is live
                </span>
              ) : (
                <button
                  className="ai-btn-primary"
                  disabled={activateMutation.isPending}
                  onClick={() => setConfirmingActivation(true)}
                  type="button"
                >
                  Make active provider
                </button>
              )}
            </div>
            {testResult ? (
              <p
                className={`ai-test-result ${testResult.ok ? "ai-test-result--ok" : "ai-test-result--fail"}`}
                role="status"
              >
                {testResult.ok ? "Connection OK: " : "Connection failed: "}
                {testResult.message}
              </p>
            ) : null}
            {confirmingActivation ? (
              <div
                aria-label="Confirm provider change"
                className="ai-activate-warning"
                role="alertdialog"
              >
                <ShieldAlert aria-hidden="true" size={18} />
                <div>
                  <strong>This changes the AI provider for every user immediately.</strong>
                  <p>
                    All intake assistant replies will be produced by {provider.label} and all
                    administrators will be notified of this change. Test the connection first.
                  </p>
                  <div className="ai-actions">
                    <button
                      className="ai-btn-primary"
                      disabled={activateMutation.isPending}
                      onClick={() => activateMutation.mutate()}
                      type="button"
                    >
                      Confirm and activate
                    </button>
                    <button
                      className="ai-btn-secondary"
                      onClick={() => setConfirmingActivation(false)}
                      type="button"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
      {actionError ? (
        <p className="auth-error" role="alert">
          {actionError}
        </p>
      ) : null}
    </section>
  );
}
