import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useEffect, useState } from "react";

import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  getWorkspacePolicy,
  saveWorkspacePolicy,
  type WorkspacePolicy,
} from "../../lib/api-client/workspace-operations";

export function WorkspaceSettingsPanel({
  configurationGrant,
  csrfToken,
  unitId,
}: {
  configurationGrant: { id: string; version: number };
  csrfToken: string;
  unitId: string;
}) {
  const queryClient = useQueryClient();
  const policy = useQuery({
    queryKey: ["workspace-policy", unitId],
    queryFn: () => getWorkspacePolicy(unitId),
    retry: false,
  });
  const [draft, setDraft] = useState<WorkspacePolicy>();
  useEffect(() => setDraft(policy.data), [policy.data]);
  const saving = useMutation({
    mutationFn: () => saveWorkspacePolicy(unitId, draft!, configurationGrant, csrfToken),
    onSuccess: (saved) => {
      setDraft(saved);
      queryClient.setQueryData(["workspace-policy", unitId], saved);
      void queryClient.invalidateQueries({ queryKey: ["workspace-overview", unitId] });
    },
  });
  // The failure check comes first: a failed load never produces a draft, so the
  // opposite order would leave the panel loading for ever.
  if (policy.isError) {
    return (
      <ErrorState
        message="Team planning settings could not be loaded."
        onRetry={() => void policy.refetch()}
      />
    );
  }
  if (policy.isLoading || !draft) return <LoadingState label="Loading team settings" />;
  const update = (values: Partial<WorkspacePolicy>) =>
    setDraft((current) => (current ? { ...current, ...values } : current));
  return (
    <section className="workspace-settings" aria-labelledby="workspace-settings-title">
      <header className="workspace-panel-heading">
        <div>
          <h4 id="workspace-settings-title">Settings</h4>
          <p>
            Configure team-level planning guardrails. Workflow approvals, access policy and quality
            controls remain authoritative.
          </p>
        </div>
      </header>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          saving.mutate();
        }}
      >
        <div className="workspace-settings__grid">
          <label>
            Work in progress limit
            <input
              max={500}
              min={1}
              onChange={(event) => update({ wipLimit: Number(event.target.value) })}
              required
              type="number"
              value={draft.wipLimit}
            />
            <small>Maximum active team work packages before the board warns.</small>
          </label>
          <label>
            Service target
            <span className="input-with-suffix">
              <input
                max={8760}
                min={1}
                onChange={(event) => update({ serviceTargetHours: Number(event.target.value) })}
                required
                type="number"
                value={draft.serviceTargetHours}
              />
              hours
            </span>
            <small>Target elapsed time for routine work, used as a planning signal.</small>
          </label>
          <label>
            Planning cadence
            <select
              onChange={(event) =>
                update({
                  planningCadence: event.target.value as WorkspacePolicy["planningCadence"],
                })
              }
              value={draft.planningCadence}
            >
              <option value="weekly">Weekly</option>
              <option value="fortnightly">Fortnightly</option>
              <option value="monthly">Monthly</option>
            </select>
          </label>
          <label>
            Planning day
            <select
              onChange={(event) => update({ planningWeekday: Number(event.target.value) })}
              value={draft.planningWeekday}
            >
              {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map(
                (day, index) => (
                  <option key={day} value={index}>
                    {day}
                  </option>
                ),
              )}
            </select>
          </label>
          <label>
            Local start time
            <input
              onChange={(event) => update({ planningLocalTime: event.target.value })}
              required
              type="time"
              value={draft.planningLocalTime.slice(0, 5)}
            />
          </label>
          <label>
            Window duration
            <span className="input-with-suffix">
              <input
                max={480}
                min={15}
                onChange={(event) =>
                  update({ planningDurationMinutes: Number(event.target.value) })
                }
                required
                step={15}
                type="number"
                value={draft.planningDurationMinutes}
              />
              minutes
            </span>
          </label>
        </div>
        <button disabled={saving.isPending} type="submit">
          <Save aria-hidden="true" size={15} />
          {saving.isPending ? "Saving settings" : "Save planning settings"}
        </button>
        {saving.isSuccess ? <p role="status">Team planning settings saved.</p> : null}
        {saving.isError ? (
          <p role="alert">Settings changed or your authority expired. Refresh and try again.</p>
        ) : null}
      </form>
    </section>
  );
}
