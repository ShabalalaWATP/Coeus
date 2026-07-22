import { Check } from "lucide-react";

import { providerStatus } from "./ai-model-panel-utils";
import type { AiModelState } from "../../lib/api-client/admin";

export function AiConfigurationSummary({ state }: { state: AiModelState }) {
  const liveProvider = state.providers.find((entry) => entry.name === state.provider);
  return (
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
          <dt>Key</dt>
          <dd>
            {state.provider === "mock"
              ? "Not required"
              : liveProvider?.apiKeyConfigured
                ? "Saved"
                : "Not saved"}
          </dd>
        </div>
        <div>
          <dt>Scope</dt>
          <dd>Text and bounded advice</dd>
        </div>
        {state.changedBy ? (
          <div>
            <dt>Last changed</dt>
            <dd>
              {state.changedBy}
              {state.changedAt ? ` · ${new Date(state.changedAt).toLocaleString("en-GB")}` : ""}
            </dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}

export function AiProviderSelector({
  disabled,
  onSelect,
  selectedProvider,
  state,
}: {
  disabled: boolean;
  onSelect: (provider: string) => void;
  selectedProvider: string;
  state: AiModelState;
}) {
  return (
    <div className="ai-provider-row" aria-label="Providers" role="group">
      {state.providers.map((provider) => {
        const status = providerStatus(provider, state.provider);
        const chosen = provider.name === selectedProvider;
        return (
          <button
            aria-pressed={chosen}
            className={`ai-provider-tab${chosen ? " ai-provider-tab--chosen" : ""}`}
            disabled={disabled}
            key={provider.name}
            onClick={() => onSelect(provider.name)}
            type="button"
          >
            <span className="ai-provider-tab__name">{provider.label}</span>
            <span className={`ai-provider-tab__status ai-provider-tab__status--${status.tone}`}>
              {status.tone === "live" ? <Check aria-hidden="true" size={12} /> : null}
              {status.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
