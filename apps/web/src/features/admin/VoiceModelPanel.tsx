import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, KeyRound, Save } from "lucide-react";
import { useEffect, useState } from "react";

import { modelInfoFor } from "./model-catalogue";
import {
  getAdminVoiceModel,
  updateAdminVoiceApiKey,
  updateAdminVoiceModel,
} from "../../lib/api-client/voice";

export function VoiceModelPanel({ csrfToken }: { csrfToken: string }) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["admin-voice-model"],
    queryFn: getAdminVoiceModel,
    retry: false,
  });
  const [model, setModel] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const mutation = useMutation({
    mutationFn: () => updateAdminVoiceModel(model, enabled, csrfToken),
    onSuccess: (state) => queryClient.setQueryData(["admin-voice-model"], state),
  });
  const keyMutation = useMutation({
    mutationFn: () => updateAdminVoiceApiKey(apiKey.trim(), csrfToken),
    onSuccess: (state) => {
      setApiKey("");
      queryClient.setQueryData(["admin-voice-model"], state);
    },
  });

  useEffect(() => {
    if (query.data) {
      setModel(query.data.model);
      setEnabled(query.data.enabled);
    }
  }, [query.data]);

  const info = modelInfoFor(model || "gpt-realtime-mini");
  return (
    <section className="surface voice-admin" aria-labelledby="voice-model-title">
      <div className="voice-admin__heading">
        <span className="chat-panel__icon">
          <AudioLines aria-hidden="true" size={20} />
        </span>
        <div>
          <span className="eyebrow">Optional voice API</span>
          <h2 id="voice-model-title">Realtime voice model</h2>
          <p>Let customers speak with Istari, then review and submit the transcript as chat.</p>
        </div>
      </div>
      {query.isLoading ? <p role="status">Loading voice settings…</p> : null}
      {query.isError ? (
        <p className="workspace-alert" role="alert">
          Voice settings are unavailable.
        </p>
      ) : null}
      {query.data ? (
        <form
          className="voice-admin__form"
          onSubmit={(event) => {
            event.preventDefault();
            mutation.mutate();
          }}
        >
          <div className="ai-step">
            <span className="ai-step__label">
              <KeyRound aria-hidden="true" size={14} />
              Dedicated Voice API key
            </span>
            <div className="ai-key-row">
              <label htmlFor="voice-api-key">
                <span className="ai-field-label">OpenAI Realtime key</span>
                <input
                  autoComplete="off"
                  id="voice-api-key"
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder={query.data.apiKeyConfigured ? "Voice key configured" : "Paste key"}
                  type="password"
                  value={apiKey}
                />
              </label>
              <button
                className="ai-btn-secondary"
                disabled={keyMutation.isPending || apiKey.trim().length < 10}
                onClick={() => keyMutation.mutate()}
                type="button"
              >
                <Save aria-hidden="true" size={16} />
                {keyMutation.isPending ? "Saving…" : "Save voice key"}
              </button>
            </div>
            <small className="field-hint">
              Admin-only and separate from every text-chat provider key. The key is never returned
              to the browser.
            </small>
          </div>
          <label htmlFor="voice-model">Voice model</label>
          <select id="voice-model" onChange={(event) => setModel(event.target.value)} value={model}>
            {(query.data.availableModels ?? []).map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
          <p className="voice-admin__description">
            <strong>{info.tier}</strong> · {info.description}
          </p>
          <label className="voice-admin__toggle">
            <input
              checked={enabled}
              disabled={!query.data.apiKeyConfigured}
              onChange={(event) => setEnabled(event.target.checked)}
              type="checkbox"
            />
            Enable Realtime voice for customer request chat
          </label>
          {!query.data.apiKeyConfigured ? (
            <small className="field-hint">
              Save the dedicated Voice API key before enabling voice.
            </small>
          ) : null}
          {keyMutation.isError ? (
            <small className="field-hint" role="alert">
              The Voice API key could not be saved.
            </small>
          ) : null}
          {mutation.isError ? (
            <small className="field-hint" role="alert">
              Voice settings could not be saved.
            </small>
          ) : null}
          {mutation.isSuccess ? (
            <small className="voice-admin__saved" role="status">
              Voice settings saved.
            </small>
          ) : null}
          <button disabled={mutation.isPending || !model} type="submit">
            <Save aria-hidden="true" size={16} />{" "}
            {mutation.isPending ? "Saving…" : "Save voice settings"}
          </button>
        </form>
      ) : null}
    </section>
  );
}
