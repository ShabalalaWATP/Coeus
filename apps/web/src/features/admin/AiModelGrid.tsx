import { Check, Plus, RefreshCw, Save } from "lucide-react";
import { useState } from "react";

import { modelInfoFor } from "./model-catalogue";
import type { AiProviderState } from "../../lib/api-client/admin";

type AiModelGridProps = {
  activeChoice: string;
  addingCustom: boolean;
  onAddCustom: (model: string, onAdded: () => void) => void;
  onApply: () => void;
  onChoose: (model: string) => void;
  onRefresh: () => void;
  pending: boolean;
  provider: AiProviderState;
  refreshing: boolean;
};

export function AiModelGrid({
  activeChoice,
  addingCustom,
  onAddCustom,
  onApply,
  onChoose,
  onRefresh,
  pending,
  provider,
  refreshing,
}: AiModelGridProps) {
  const [customModel, setCustomModel] = useState("");
  const customModelId = `${provider.name}-custom-model`;

  return (
    <div className="ai-model-configuration">
      <div className="ai-model-tools">
        {provider.supportsModelRefresh ? (
          <div className="ai-model-refresh">
            <button
              aria-label={`Refresh models from ${provider.label}`}
              className="ai-btn-secondary"
              disabled={pending || refreshing || !provider.apiKeyConfigured}
              onClick={onRefresh}
              type="button"
            >
              <RefreshCw aria-hidden="true" size={15} />
              {refreshing ? "Refreshing" : "Refresh from provider"}
            </button>
            {!provider.apiKeyConfigured ? (
              <span className="ai-model-refresh__hint">Save a key before refreshing.</span>
            ) : null}
          </div>
        ) : null}
        {provider.name !== "gemini_api" &&
        (provider.name !== "openai_api" || provider.supportsModelRefresh) ? (
          <form
            className="ai-custom-model"
            onSubmit={(event) => {
              event.preventDefault();
              const model = customModel.trim();
              if (model.length >= 2) {
                onAddCustom(model, () => setCustomModel(""));
              }
            }}
          >
            <label className="sr-only" htmlFor={customModelId}>
              {provider.label} model ID
            </label>
            <input
              aria-label={`${provider.label} model ID`}
              disabled={pending}
              id={customModelId}
              onChange={(event) => setCustomModel(event.target.value)}
              placeholder="Add a model ID (for example, a new release)"
              value={customModel}
            />
            <button
              aria-label={`Add model ID for ${provider.label}`}
              className="ai-btn-secondary"
              disabled={pending || addingCustom || customModel.trim().length < 2}
              type="submit"
            >
              <Plus aria-hidden="true" size={15} />
              Add
            </button>
          </form>
        ) : null}
      </div>
      <form
        className="ai-model-selection"
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
                  disabled={pending}
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
        <button
          className="ai-btn-secondary"
          disabled={pending || activeChoice === provider.activeModel}
          type="submit"
        >
          <Save aria-hidden="true" size={16} />
          Apply model
        </button>
      </form>
    </div>
  );
}
