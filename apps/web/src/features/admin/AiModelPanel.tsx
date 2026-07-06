import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrainCircuit, Check, Save } from "lucide-react";
import { useState } from "react";

import { modelInfoFor } from "./model-catalogue";
import { ErrorState, LoadingState } from "../../components/ui/PageState";
import { getAiModelState, selectAiModel, type AiModelState } from "../../lib/api-client/admin";

type AiModelPanelProps = {
  csrfToken: string;
};

export function AiModelPanel({ csrfToken }: AiModelPanelProps) {
  const queryClient = useQueryClient();
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [saveError, setSaveError] = useState(false);
  const stateQuery = useQuery({ queryKey: ["ai-model"], queryFn: getAiModelState });
  const saveMutation = useMutation({
    mutationFn: (model: string) => selectAiModel(model, csrfToken),
    onSuccess: (state: AiModelState) => {
      setSaveError(false);
      setSelectedModel(null);
      queryClient.setQueryData(["ai-model"], state);
    },
    onError: () => setSaveError(true),
  });
  const state = stateQuery.data;
  const activeChoice = selectedModel ?? state?.activeModel ?? "";

  return (
    <section className="surface ai-model-panel" aria-labelledby="ai-model-title">
      <div className="section-heading access-heading">
        <BrainCircuit aria-hidden="true" size={20} />
        <div>
          <h2 id="ai-model-title">AI model</h2>
          <p>Choose the Gemini model every Istari agent uses for extraction, search and routing.</p>
        </div>
      </div>
      {stateQuery.isError ? <ErrorState onRetry={() => void stateQuery.refetch()} /> : null}
      {stateQuery.isLoading ? <LoadingState label="Loading model configuration" /> : null}
      {state ? (
        <form
          className="ai-model-form"
          onSubmit={(event) => {
            event.preventDefault();
            saveMutation.mutate(activeChoice);
          }}
        >
          <div aria-label="Available models" className="ai-model-grid" role="radiogroup">
            {state.availableModels.map((model) => {
              const info = modelInfoFor(model);
              const isActive = model === state.activeModel;
              const isChosen = model === activeChoice;
              return (
                <label
                  className={`ai-model-card${isChosen ? " ai-model-card--chosen" : ""}`}
                  key={model}
                >
                  <input
                    checked={isChosen}
                    name="ai-model"
                    onChange={() => setSelectedModel(model)}
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
          <button
            disabled={saveMutation.isPending || activeChoice === state.activeModel}
            type="submit"
          >
            <Save aria-hidden="true" size={16} />
            Apply model
          </button>
          <p className="ai-model-provider">
            Provider: <code>{state.provider}</code>
            {state.provider === "mock"
              ? " (local mock; the selection applies to deployed Vertex AI environments)"
              : null}
            {state.changedBy
              ? ` — last changed by ${state.changedBy}${
                  state.changedAt ? ` on ${new Date(state.changedAt).toLocaleString("en-GB")}` : ""
                }`
              : null}
          </p>
        </form>
      ) : null}
      {saveError ? (
        <p className="auth-error" role="alert">
          The model could not be changed. Refresh and try again.
        </p>
      ) : null}
    </section>
  );
}
