import { Check, Save } from "lucide-react";

import { modelInfoFor } from "./model-catalogue";
import type { AiProviderState } from "../../lib/api-client/admin";

type AiModelGridProps = {
  activeChoice: string;
  onApply: () => void;
  onChoose: (model: string) => void;
  pending: boolean;
  provider: AiProviderState;
};

export function AiModelGrid({
  activeChoice,
  onApply,
  onChoose,
  pending,
  provider,
}: AiModelGridProps) {
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
