import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, KeyRound, PlugZap, Save } from "lucide-react";
import { useEffect, useState } from "react";

import { AdminDisclosureSummary } from "./AdminDisclosureSummary";
import { modelInfoFor } from "./model-catalogue";
import {
  getAdminVoiceModel,
  testAdminVoiceConnection,
  updateAdminVoiceApiKey,
  updateAdminVoiceModel,
} from "../../lib/api-client/voice";

export function VoiceModelPanel({
  csrfToken,
  initiallyOpen = true,
}: {
  csrfToken: string;
  initiallyOpen?: boolean;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(initiallyOpen);
  const query = useQuery({
    queryKey: ["admin-voice-model"],
    queryFn: getAdminVoiceModel,
    retry: false,
  });
  const [model, setModel] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [testedModel, setTestedModel] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => updateAdminVoiceModel(model, enabled, csrfToken),
    onMutate: () => clearTest(),
    onSuccess: (state) => queryClient.setQueryData(["admin-voice-model"], state),
  });
  const keyMutation = useMutation({
    mutationFn: () => updateAdminVoiceApiKey(apiKey.trim(), csrfToken),
    onMutate: () => clearTest(),
    onSuccess: (state) => {
      setApiKey("");
      queryClient.setQueryData(["admin-voice-model"], state);
    },
  });
  const testMutation = useMutation({
    mutationFn: () => testAdminVoiceConnection(csrfToken),
    onSuccess: (result) => setTestedModel(result.ok ? result.model : null),
  });

  function clearTest() {
    testMutation.reset();
    setTestedModel(null);
  }

  useEffect(() => {
    if (query.data) {
      setModel(query.data.model);
      setEnabled(query.data.enabled);
    }
  }, [query.data]);

  const info = modelInfoFor(model || "gpt-realtime-2.1");
  const state = query.data;
  const savedDraft = Boolean(state) && model === state?.model && apiKey.trim() === "";
  const connectionTested =
    Boolean(state) && savedDraft && testMutation.data?.ok === true && testedModel === state?.model;
  const actionPending = mutation.isPending || keyMutation.isPending || testMutation.isPending;
  return (
    <details
      className="surface admin-disclosure voice-admin"
      onToggle={(event) => setOpen(event.currentTarget.open)}
      open={open}
    >
      <AdminDisclosureSummary
        description="Let customers speak with Istari and review the transcript before sending."
        eyebrow="Optional voice API"
        icon={AudioLines}
        statuses={[
          state?.apiKeyConfigured
            ? { label: "Key saved", tone: "active" }
            : { label: "No key saved", tone: "attention" },
          state ? { label: state.model, tone: "neutral" } : { label: "Loading model" },
          state?.enabled ? { label: "Voice active", tone: "active" } : { label: "Voice disabled" },
          ...(connectionTested
            ? [{ label: `Tested ${state?.model ?? "voice"}`, tone: "active" as const }]
            : []),
        ]}
        title="Realtime voice model"
        titleId="voice-model-title"
      />
      <div className="admin-disclosure__body">
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
                    disabled={actionPending}
                    onChange={(event) => {
                      setApiKey(event.target.value);
                      clearTest();
                    }}
                    placeholder={query.data.apiKeyConfigured ? "Voice key configured" : "Paste key"}
                    type="password"
                    value={apiKey}
                  />
                </label>
                <button
                  className="ai-btn-secondary"
                  disabled={actionPending || apiKey.trim().length < 10}
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
              <p
                className={`admin-key-state ${query.data.apiKeyConfigured ? "admin-key-state--saved" : ""}`}
              >
                {query.data.apiKeyConfigured
                  ? "A dedicated OpenAI Realtime key is saved. Test it below to verify access."
                  : "No dedicated OpenAI Realtime key is saved."}
              </p>
            </div>
            <label htmlFor="voice-model">Voice model</label>
            <select
              id="voice-model"
              disabled={actionPending}
              onChange={(event) => {
                setModel(event.target.value);
                clearTest();
              }}
              value={model}
            >
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
                disabled={actionPending || !query.data.apiKeyConfigured}
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
            <div className="voice-admin__actions">
              <button
                className="ai-btn-secondary"
                disabled={actionPending || !query.data.apiKeyConfigured || !savedDraft}
                onClick={() => testMutation.mutate()}
                type="button"
              >
                <PlugZap aria-hidden="true" size={16} />
                {testMutation.isPending ? "Testing connection" : "Test connection"}
              </button>
              {testMutation.data ? (
                <p
                  className={`ai-test-result ai-test-result--${testMutation.data.ok ? "ok" : "fail"}`}
                  role={testMutation.data.ok ? "status" : "alert"}
                >
                  {testMutation.data.ok ? "Connection OK: " : "Connection failed: "}
                  {testMutation.data.message}
                </p>
              ) : null}
              {testMutation.isError ? (
                <p className="ai-test-result ai-test-result--fail" role="alert">
                  The voice connection test could not be run.
                </p>
              ) : null}
              {!savedDraft ? (
                <small className="field-hint">Save or clear draft changes before testing.</small>
              ) : null}
            </div>
            <button disabled={actionPending || !model} type="submit">
              <Save aria-hidden="true" size={16} />{" "}
              {mutation.isPending ? "Saving…" : "Save voice settings"}
            </button>
          </form>
        ) : null}
      </div>
    </details>
  );
}
