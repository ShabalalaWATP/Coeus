import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, Check, PlugZap, Save, ShieldAlert } from "lucide-react";
import { useState } from "react";

import { modelInfoFor } from "./model-catalogue";
import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  configureAiApiKey,
  getAiModelState,
  selectAiModel,
  selectAiProvider,
  testAiConnection,
  type AiConnectionTest,
  type AiModelState,
  type AiProviderState,
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
  const [confirmingActivation, setConfirmingActivation] = useState(false);
  const { actionError, clearActionError, failActionWith } = useActionError();
  const stateQuery = useQuery({ queryKey: ["ai-model"], queryFn: getAiModelState });
  const state = stateQuery.data;
  const providerName = selectedProvider ?? state?.provider ?? "gemini_api";
  const provider = state?.providers.find((entry) => entry.name === providerName);
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
  const pickProvider = (name: string) => {
    setSelectedProvider(name);
    setSelectedModel(null);
    setApiKey("");
    setTestResult(null);
    setConfirmingActivation(false);
    clearActionError();
  };
  const activeChoice = selectedModel ?? provider?.activeModel ?? "";

  return (
    <section className="surface ai-model-panel" aria-labelledby="ai-model-title">
      <div className="section-heading access-heading">
        <BrainCircuit aria-hidden="true" size={20} />
        <div>
          <h2 id="ai-model-title">AI provider and model</h2>
          <p>
            Gemini API is the primary provider; OpenAI, GCP Vertex AI and AWS Bedrock are optional
            alternatives. Search embeddings are configured separately.
          </p>
        </div>
      </div>
      {stateQuery.isError ? <ErrorState onRetry={() => void stateQuery.refetch()} /> : null}
      {stateQuery.isLoading ? <LoadingState label="Loading model configuration" /> : null}
      {state && provider ? (
        <div className="ai-model-form">
          <div aria-label="Providers" className="ai-provider-row" role="tablist">
            {state.providers.map((entry) => (
              <button
                aria-selected={entry.name === providerName}
                className={`ai-provider-tab${
                  entry.name === providerName ? " ai-provider-tab--chosen" : ""
                }`}
                key={entry.name}
                onClick={() => pickProvider(entry.name)}
                role="tab"
                type="button"
              >
                {entry.label}
                {entry.name === state.provider ? (
                  <span className="ai-model-card__active">
                    <Check aria-hidden="true" size={13} />
                    Live
                  </span>
                ) : null}
              </button>
            ))}
          </div>
          {provider.name !== "mock" ? (
            <ModelGrid
              activeChoice={activeChoice}
              onApply={() => modelMutation.mutate(activeChoice)}
              onChoose={setSelectedModel}
              pending={modelMutation.isPending}
              provider={provider}
            />
          ) : (
            <p className="ai-model-provider">
              The mock provider answers locally with deterministic replies and needs no key.
            </p>
          )}
          {provider.name !== "mock" ? (
            <div className="ai-key-row">
              <label>
                {provider.label} API key
                <input
                  autoComplete="off"
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder={provider.apiKeyConfigured ? "API key configured" : "Paste API key"}
                  type="password"
                  value={apiKey}
                />
              </label>
              <button
                disabled={keyMutation.isPending || apiKey.trim().length < 10}
                onClick={() => keyMutation.mutate(apiKey.trim())}
                type="button"
              >
                <Save aria-hidden="true" size={16} />
                Save key
              </button>
            </div>
          ) : null}
          <div className="ai-key-row">
            <button
              disabled={testMutation.isPending}
              onClick={() => testMutation.mutate()}
              type="button"
            >
              <PlugZap aria-hidden="true" size={16} />
              {testMutation.isPending ? "Testing connection" : "Test connection"}
            </button>
            {provider.name !== state.provider ? (
              <button
                disabled={activateMutation.isPending}
                onClick={() => setConfirmingActivation(true)}
                type="button"
              >
                Make active provider
              </button>
            ) : null}
          </div>
          {testResult ? (
            <p
              className={testResult.ok ? "ai-test-result ai-test-result--ok" : "auth-error"}
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
                <div className="ai-key-row">
                  <button
                    disabled={activateMutation.isPending}
                    onClick={() => activateMutation.mutate()}
                    type="button"
                  >
                    Confirm and activate
                  </button>
                  <button onClick={() => setConfirmingActivation(false)} type="button">
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          ) : null}
          <p className="ai-model-provider">
            Live provider: <code>{state.provider}</code>
            {` | live model: ${state.activeModel}`}
            {` | embeddings: ${state.embeddingProvider}`}
            {` | embedded products: ${state.embeddedProductCount}`}
            {state.changedBy
              ? ` | last changed by ${state.changedBy}${
                  state.changedAt ? ` on ${new Date(state.changedAt).toLocaleString("en-GB")}` : ""
                }`
              : null}
          </p>
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

type ModelGridProps = {
  activeChoice: string;
  onApply: () => void;
  onChoose: (model: string) => void;
  pending: boolean;
  provider: AiProviderState;
};

function ModelGrid({ activeChoice, onApply, onChoose, pending, provider }: ModelGridProps) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
    >
      <div aria-label="Available models" className="ai-model-grid" role="radiogroup">
        {provider.models.map((model) => {
          const info = modelInfoFor(model);
          const isActive = model === provider.activeModel;
          const isChosen = model === activeChoice;
          return (
            <label
              className={`ai-model-card${isChosen ? " ai-model-card--chosen" : ""}`}
              key={model}
            >
              <input
                checked={isChosen}
                name="ai-model"
                onChange={() => onChoose(model)}
                type="radio"
                value={model}
              />
              <span className="ai-model-card__header">
                <code>{model}</code>
                <span className={`ai-model-tier ai-model-tier--${info.tier.toLowerCase()}`}>
                  {info.tier}
                </span>
              </span>
              <span className="ai-model-card__description">{info.description}</span>
              {isActive ? (
                <span className="ai-model-card__active">
                  <Check aria-hidden="true" size={13} />
                  Active
                </span>
              ) : null}
            </label>
          );
        })}
      </div>
      <button disabled={pending || activeChoice === provider.activeModel} type="submit">
        <Save aria-hidden="true" size={16} />
        Apply model
      </button>
    </form>
  );
}
