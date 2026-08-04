import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Check } from "lucide-react";
import { useState } from "react";

import {
  acknowledgeWorkUpdate,
  getWorkUpdatePreferences,
  getWorkUpdates,
  saveWorkUpdatePreferences,
  type Preferences,
} from "../../lib/api-client/workspace-productivity";

const labels: Record<string, string> = {
  assignment: "Work assigned",
  mention: "You were mentioned",
  due_soon: "Work is due soon",
  blocked_review: "Blocked work needs review",
  returned: "Work was returned",
  transfer_request: "Transfer needs attention",
  calendar_conflict: "Calendar conflict",
  delegation_expiry: "Delegated access is expiring",
};

export function WorkUpdatesPanel({ csrfToken }: { csrfToken: string }) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const updates = useQuery({
    queryKey: ["work-updates"],
    queryFn: getWorkUpdates,
    enabled: open,
    retry: false,
  });
  const preferences = useQuery({
    queryKey: ["work-update-preferences"],
    queryFn: getWorkUpdatePreferences,
    enabled: open,
    retry: false,
  });
  const acknowledge = useMutation({
    mutationFn: (updateId: string) => acknowledgeWorkUpdate(updateId, csrfToken),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["work-updates"],
      }),
  });
  const savePreferences = useMutation({
    mutationFn: (value: Preferences) => saveWorkUpdatePreferences(value, csrfToken),
    onSuccess: () =>
      void queryClient.invalidateQueries({
        queryKey: ["work-update-preferences"],
      }),
  });

  return (
    <details
      className="workspace-productivity work-updates"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <Bell aria-hidden="true" size={16} /> Work updates
      </summary>
      <p>Updates contain only a type and a link identifier that you can currently access.</p>
      {updates.isError ? <p role="alert">Work updates are not available.</p> : null}
      <ul>
        {updates.data?.items.map((item) => (
          <li key={item.updateId}>
            <span>
              <strong>{labels[item.kind] ?? "Work update"}</strong>
              <small>{new Date(item.occurredAt).toLocaleString()}</small>
            </span>
            {item.acknowledgedAt ? (
              <span>Read</span>
            ) : (
              <button
                disabled={acknowledge.isPending}
                onClick={() => acknowledge.mutate(item.updateId)}
                type="button"
              >
                <Check aria-hidden="true" size={15} /> Mark read
              </button>
            )}
          </li>
        ))}
      </ul>
      {updates.isSuccess && updates.data.items.length === 0 ? <p>No current updates.</p> : null}
      {preferences.data ? (
        <fieldset disabled={savePreferences.isPending}>
          <legend>Delivery preferences</legend>
          <label>
            Presentation
            <select
              onChange={(event) =>
                savePreferences.mutate({
                  ...preferences.data,
                  mode: event.target.value as Preferences["mode"],
                })
              }
              value={preferences.data.mode}
            >
              <option value="immediate">Immediate</option>
              <option value="digest">Digest</option>
            </select>
          </label>
          <label>
            <input
              checked={preferences.data.dueReminders}
              onChange={(event) =>
                savePreferences.mutate({
                  ...preferences.data,
                  dueReminders: event.target.checked,
                })
              }
              type="checkbox"
            />{" "}
            Include due-date reminders
          </label>
        </fieldset>
      ) : null}
      {acknowledge.isError || savePreferences.isError ? (
        <p role="alert">The update could not be saved.</p>
      ) : null}
    </details>
  );
}
