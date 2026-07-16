import { BrainCircuit, Check, KeyRound, PlugZap, Save, Sparkles } from "lucide-react";

import { AiModelGrid } from "./AiModelGrid";
import { AiConfigurationSummary, AiProviderSelector } from "./AiConfigurationSummary";
import { AiProviderActivationWarning } from "./AiProviderActivationWarning";
import { useAiModelPanelController } from "./useAiModelPanelController";
import { ErrorState, LoadingState } from "../../components/ui/PageState";

type AiModelPanelProps = {
  csrfToken: string;
};

export function AiModelPanel({ csrfToken }: AiModelPanelProps) {
  const {
    stateQuery,
    state,
    providerName,
    provider,
    apiKey,
    setApiKey,
    testResult,
    modelNote,
    confirmingActivation,
    setConfirmingActivation,
    activateButtonRef,
    actionError,
    modelMutation,
    keyMutation,
    testMutation,
    activateMutation,
    refreshMutation,
    customMutation,
    pickProvider,
    activeChoice,
    setSelectedModel,
    setTestResult,
    setTestedConfiguration,
    isLive,
    isMock,
    activationTested,
    configurationPending,
  } = useAiModelPanelController(csrfToken);

  return (
    <section className="surface ai-model-panel" aria-labelledby="ai-model-title">
      <div className="section-heading access-heading">
        <BrainCircuit aria-hidden="true" size={20} />
        <div>
          <h2 id="ai-model-title">AI provider and model</h2>
          <p>
            Gemini API is the primary provider; OpenAI, GCP Vertex AI and AWS Bedrock are optional
            alternatives. Gemini and OpenAI use current curated catalogues; deployment-specific
            Vertex AI and Bedrock model IDs can be added by hand. Search embeddings are configured
            separately.
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
