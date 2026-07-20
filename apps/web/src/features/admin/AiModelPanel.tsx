import { BrainCircuit, Check, KeyRound, PlugZap, Save, Sparkles } from "lucide-react";
import { useState } from "react";

import { AdminDisclosureSummary } from "./AdminDisclosureSummary";
import { AiModelGrid } from "./AiModelGrid";
import { AiConfigurationSummary, AiProviderSelector } from "./AiConfigurationSummary";
import { AiProviderActivationWarning } from "./AiProviderActivationWarning";
import { useAiModelPanelController } from "./useAiModelPanelController";
import { ErrorState, LoadingState } from "../../components/ui/PageState";

type AiModelPanelProps = {
  csrfToken: string;
  initiallyOpen?: boolean;
};

export function AiModelPanel({ csrfToken, initiallyOpen = true }: AiModelPanelProps) {
  const [open, setOpen] = useState(initiallyOpen);
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
    testedConfiguration,
    testReady,
    configurationPending,
  } = useAiModelPanelController(csrfToken);
  const liveProvider = state?.providers.find((entry) => entry.name === state.provider);
  const liveKeyLabel =
    state?.provider === "mock"
      ? "No key required"
      : liveProvider?.apiKeyConfigured
        ? "Key saved"
        : "No key saved";
  const liveConfigurationTested =
    testResult?.ok === true &&
    Boolean(liveProvider) &&
    testedConfiguration === `${state?.provider}:${liveProvider?.activeModel}`;

  return (
    <details
      className="surface admin-disclosure ai-model-panel"
      onToggle={(event) => setOpen(event.currentTarget.open)}
      open={open}
    >
      <AdminDisclosureSummary
        description="Choose the text-chat provider and model used by Istari."
        eyebrow="Required AI provider"
        icon={BrainCircuit}
        statuses={[
          {
            label: state ? `${liveProvider?.label ?? state.provider} active` : "Loading provider",
            tone: state ? "active" : "neutral",
          },
          {
            label: liveKeyLabel,
            tone:
              liveKeyLabel === "Key saved" || liveKeyLabel === "No key required"
                ? "active"
                : "attention",
          },
          state
            ? { label: liveProvider?.activeModel ?? state.activeModel }
            : { label: "Loading model" },
          ...(liveConfigurationTested
            ? [
                {
                  label: `Tested ${liveProvider?.activeModel ?? state?.activeModel}`,
                  tone: "active" as const,
                },
              ]
            : []),
        ]}
        title="AI provider and model"
        titleId="ai-model-title"
      />
      <div className="admin-disclosure__body">
        <p className="admin-section-intro">
          Gemini API is the primary provider; OpenAI, GCP Vertex AI and AWS Bedrock are optional
          alternatives. Search embeddings and Realtime voice are configured separately.
        </p>
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
                  disabled={configurationPending || !testReady}
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
              {!testReady ? (
                <p className="ai-hint" role="status">
                  Save or clear draft key and model changes before testing.
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
      </div>
    </details>
  );
}
