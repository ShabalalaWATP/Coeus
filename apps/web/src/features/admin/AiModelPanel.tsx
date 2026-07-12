import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, Check, KeyRound, PlugZap, Save, Sparkles } from "lucide-react";
import { useRef, useState } from "react";

import { AiModelGrid } from "./AiModelGrid";
import { AiConfigurationSummary, AiProviderSelector } from "./AiConfigurationSummary";
import { AiProviderActivationWarning } from "./AiProviderActivationWarning";
import { type ModelNote } from "./ai-model-panel-utils";
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
import { actionErrorMessage, useActionError } from "../../lib/mutations/action-error";

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
  const [testedConfiguration, setTestedConfiguration] = useState<string | null>(null);
  const activateButtonRef = useRef<HTMLButtonElement>(null);
  const { actionError, clearActionError, failActionWith } = useActionError();
  const stateQuery = useQuery({ queryKey: ["ai-model"], queryFn: getAiModelState });
  const state = stateQuery.data;
  const providerName = selectedProvider ?? state?.provider ?? "gemini_api";
  const provider = state?.providers.find((entry) => entry.name === providerName);
  const applyState = (next: AiModelState) => queryClient.setQueryData(["ai-model"], next);
  const modelMutation = useMutation({
    mutationFn: (model: string) => selectAiModel(model, providerName, csrfToken),
    onError: failActionWith("The model could not be changed. Refresh and try again."),
    onMutate: () => {
      clearActionError();
      setTestResult(null);
      setTestedConfiguration(null);
    },
    onSuccess: (next: AiModelState) => {
      setSelectedModel(null);
      applyState(next);
    },
  });
  const keyMutation = useMutation({
    mutationFn: (key: string) => configureAiApiKey(key, providerName, csrfToken),
    onError: failActionWith("The API key could not be saved. Check the key and try again."),
    onMutate: () => {
      clearActionError();
      setTestResult(null);
      setTestedConfiguration(null);
    },
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
      setTestedConfiguration(null);
    },
    onSuccess: (result) => {
      setTestResult(result);
      setTestedConfiguration(result.ok ? configurationKey(providerName, result.model) : null);
    },
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
      setTestResult(null);
      setTestedConfiguration(null);
    },
    onError: (error) =>
      setModelNote({
        tone: "fail",
        text: actionErrorMessage(error, "Could not refresh models."),
      }),
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
      setTestResult(null);
      setTestedConfiguration(null);
    },
    onError: (error) =>
      setModelNote({
        tone: "fail",
        text: actionErrorMessage(error, "That model ID could not be added."),
      }),
    onSuccess: (next: AiModelState, model: string) => {
      applyState(next);
      setSelectedModel(model);
      setModelNote({
        tone: "ok",
        text: `Added ${model}. Choose Apply model to make it active.`,
      });
    },
  });
  const pickProvider = (name: string) => {
    setSelectedProvider(name);
    setSelectedModel(null);
    setApiKey("");
    setTestResult(null);
    setTestedConfiguration(null);
    setModelNote(null);
    setConfirmingActivation(false);
    clearActionError();
  };
  const activeChoice = selectedModel ?? provider?.activeModel ?? "";
  const isLive = provider?.name === state?.provider;
  const isMock = provider?.name === "mock";
  const currentConfiguration = provider ? configurationKey(provider.name, activeChoice) : "";
  const activationTested = testedConfiguration === currentConfiguration;
  const configurationPending =
    modelMutation.isPending ||
    keyMutation.isPending ||
    testMutation.isPending ||
    activateMutation.isPending ||
    refreshMutation.isPending ||
    customMutation.isPending;

  return (
    <section className="surface ai-model-panel" aria-labelledby="ai-model-title">
      <div className="section-heading access-heading">
        <BrainCircuit aria-hidden="true" size={20} />
        <div>
          <h2 id="ai-model-title">AI provider and model</h2>
          <p>
            Gemini API is the primary provider; OpenAI, GCP Vertex AI and AWS Bedrock are optional
            alternatives. Refresh the model list from a provider or add a new model ID by hand to
            stay current. Search embeddings are configured separately.
          </p>
        </div>
      </div>
      {stateQuery.isError ? <ErrorState onRetry={() => void stateQuery.refetch()} /> : null}
      {stateQuery.isLoading ? <LoadingState label="Loading model configuration" /> : null}
      {state && provider ? (
        <div className="ai-model-body">
          <AiConfigurationSummary state={state} />
          <AiProviderSelector
            disabled={configurationPending}
            onSelect={pickProvider}
            selectedProvider={providerName}
            state={state}
          />

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
                    Step 1: API key
                  </span>
                  <form
                    className="ai-key-row"
                    onSubmit={(event) => {
                      event.preventDefault();
                      if (apiKey.trim().length >= 10) keyMutation.mutate(apiKey.trim());
                    }}
                  >
                    <label>
                      <span className="ai-field-label">{provider.label} key</span>
                      <input
                        aria-label={`${provider.label} key`}
                        autoComplete="off"
                        disabled={configurationPending}
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
                      disabled={configurationPending || apiKey.trim().length < 10}
                      type="submit"
                    >
                      <Save aria-hidden="true" size={16} />
                      Save key
                    </button>
                  </form>
                </div>
                <div className="ai-step">
                  <span className="ai-step__label">
                    <Sparkles aria-hidden="true" size={14} />
                    Step 2: Model
                  </span>
                  <AiModelGrid
                    activeChoice={activeChoice}
                    addingCustom={customMutation.isPending}
                    key={provider.name}
                    onAddCustom={(model, onAdded) =>
                      customMutation.mutate(model, { onSuccess: onAdded })
                    }
                    onApply={() => modelMutation.mutate(activeChoice)}
                    onChoose={(model) => {
                      setSelectedModel(model);
                      setTestResult(null);
                      setTestedConfiguration(null);
                    }}
                    onRefresh={() => refreshMutation.mutate()}
                    pending={configurationPending}
                    provider={provider}
                    refreshing={refreshMutation.isPending}
                  />
                  {modelNote ? (
                    <p
                      className={`ai-model-note ai-model-note--${modelNote.tone}`}
                      role={modelNote.tone === "fail" ? "alert" : "status"}
                    >
                      {modelNote.text}
                    </p>
                  ) : null}
                </div>
              </>
            )}
            <div className="ai-actions">
              <button
                className="ai-btn-secondary"
                disabled={configurationPending}
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
                  disabled={
                    configurationPending ||
                    (!isMock && !provider.apiKeyConfigured) ||
                    !activationTested
                  }
                  onClick={() => setConfirmingActivation(true)}
                  ref={activateButtonRef}
                  type="button"
                >
                  Make active provider
                </button>
              )}
            </div>
            {!isLive && !activationTested ? (
              <p className="ai-hint" role="status">
                Test this provider and its selected model successfully before activation.
              </p>
            ) : null}
            {testResult ? (
              <p
                className={`ai-test-result ${testResult.ok ? "ai-test-result--ok" : "ai-test-result--fail"}`}
                role={testResult.ok ? "status" : "alert"}
              >
                {testResult.ok ? "Connection OK: " : "Connection failed: "}
                {testResult.message}
              </p>
            ) : null}
            {confirmingActivation ? (
              <AiProviderActivationWarning
                onCancel={() => {
                  setConfirmingActivation(false);
                  requestAnimationFrame(() => activateButtonRef.current?.focus());
                }}
                onConfirm={() => activateMutation.mutate()}
                pending={activateMutation.isPending}
                providerLabel={provider.label}
              />
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

function configurationKey(provider: string, model: string) {
  return `${provider}:${model}`;
}
