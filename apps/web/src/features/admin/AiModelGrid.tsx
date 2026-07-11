import { Check, Plus, RefreshCw, Save } from "lucide-react";
import { useState } from "react";

import { modelInfoFor } from "./model-catalogue";
import type { AiProviderState } from "../../lib/api-client/admin";

type AiModelGridProps = {
  activeChoice: string;
  addingCustom: boolean;
  onAddCustom: (model: string) => void;
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

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
    >
      <div className="ai-model-tools">
        <button
          className="ai-btn-secondary"
          disabled={refreshing}
          onClick={onRefresh}
          type="button"
        >
          <RefreshCw aria-hidden="true" size={15} />
          {refreshing ? "Refreshing" : "Refresh from provider"}
        </button>
        <div className="ai-custom-model">
          <input
            aria-label="Add a model id"
            onChange={(event) => setCustomModel(event.target.value)}
            placeholder="Add a model id (e.g. a brand-new release)"
            value={customModel}
          />
          <button
            className="ai-btn-secondary"
            disabled={addingCustom || customModel.trim().length < 2}
            onClick={() => {
              onAddCustom(customModel.trim());
              setCustomModel("");
            }}
            type="button"
          >
            <Plus aria-hidden="true" size={15} />
            Add
          </button>
        </div>
      </div>
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
      <button
        className="ai-btn-secondary"
        disabled={pending || activeChoice === provider.activeModel}
        type="submit"
      >
        <Save aria-hidden="true" size={16} />
        Apply model
      </button>
    </form>
  );
}
