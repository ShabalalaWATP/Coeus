import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  addAccessGroupAdmin,
  listAccessGroupAdmins,
  removeAccessGroupAdmin,
  searchAccessGroupDirectory,
  type AccessGroupSummary,
} from "../../lib/api-client/access-groups";
import { actionErrorMessage } from "../../lib/mutations/action-error";

const MAX_ADMINS = 8;

export function AccessGroupAdminPanel({
  csrfToken,
  groups,
}: {
  csrfToken: string;
  groups: AccessGroupSummary[];
}) {
  const queryClient = useQueryClient();
  const [groupId, setGroupId] = useState(groups[0]?.id ?? "");
  const [search, setSearch] = useState("");
  const [message, setMessage] = useState<{ tone: "ok" | "fail"; text: string } | null>(null);
  const adminsQuery = useQuery({
    enabled: groupId !== "",
    queryKey: ["access-group-admins", groupId],
    queryFn: () => listAccessGroupAdmins(groupId),
  });
  const directoryQuery = useQuery({
    enabled: search.trim().length >= 3,
    queryKey: ["access-group-directory", search.trim()],
    queryFn: () => searchAccessGroupDirectory(search.trim()),
  });
  const admins = adminsQuery.data ?? [];
  const directoryUsers = directoryQuery.data?.users ?? [];
  const candidates = directoryUsers.filter(
    (candidate) => !admins.some((admin) => admin.id === candidate.id),
  );
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["access-group-admins", groupId] });
  const addMutation = useMutation({
    mutationFn: (userId: string) => addAccessGroupAdmin(groupId, userId, csrfToken),
    onMutate: () => setMessage(null),
    onError: (error) =>
      setMessage({
        tone: "fail",
        text: actionErrorMessage(error, "The group administrator could not be added."),
      }),
    onSuccess: async () => {
      setSearch("");
      setMessage({ tone: "ok", text: "Group administrator added." });
      await refresh();
    },
  });
  const removeMutation = useMutation({
    mutationFn: (userId: string) => removeAccessGroupAdmin(groupId, userId, csrfToken),
    onMutate: () => setMessage(null),
    onError: (error) =>
      setMessage({
        tone: "fail",
        text: actionErrorMessage(error, "The group administrator could not be removed."),
      }),
    onSuccess: async () => {
      setMessage({ tone: "ok", text: "Group administrator removed." });
      await refresh();
    },
  });
  const pending = addMutation.isPending || removeMutation.isPending;

  return (
    <section className="surface access-group-admins" aria-labelledby="access-group-admins-title">
      <h2 id="access-group-admins-title">Group administrators</h2>
      <p>
        Delegated authority permits application review. It does not grant group membership or access
        to protected content. Each group may have up to {MAX_ADMINS} administrators.
      </p>
      <label>
        Access group
        <select
          disabled={pending}
          onChange={(event) => {
            setGroupId(event.target.value);
            setSearch("");
            setMessage(null);
          }}
          value={groupId}
        >
          {groups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.name}
            </option>
          ))}
        </select>
      </label>
      {adminsQuery.isLoading ? <p role="status">Loading group administrators…</p> : null}
      {adminsQuery.isError ? <p role="alert">Group administrators could not be loaded.</p> : null}
      <ul>
        {admins.map((admin) => (
          <li key={admin.id}>
            <span>
              <strong>{admin.displayName}</strong>
              <small>{admin.username}</small>
            </span>
            <button
              aria-label={`Remove ${admin.displayName} as group administrator`}
              disabled={pending}
              onClick={() => {
                if (window.confirm(`Remove ${admin.displayName} as a group administrator?`)) {
                  removeMutation.mutate(admin.id);
                }
              }}
              type="button"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
      {admins.length < MAX_ADMINS ? (
        <div>
          <label>
            Find an active user
            <input
              disabled={pending}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Name or username"
              value={search}
            />
          </label>
          {directoryQuery.isLoading ? <p role="status">Searching active users…</p> : null}
          {directoryQuery.isError ? (
            <p role="alert">The user directory could not be loaded.</p>
          ) : null}
          {directoryQuery.isSuccess && directoryQuery.data.total === 0 ? (
            <p>No active users match this search.</p>
          ) : null}
          {directoryQuery.data && directoryQuery.data.total > directoryUsers.length ? (
            <p>More users match. Refine the name or username.</p>
          ) : null}
          {candidates.length ? (
            <ul aria-label="Matching active users">
              {candidates.map((user) => (
                <li key={user.id}>
                  <button
                    disabled={pending}
                    onClick={() => addMutation.mutate(user.id)}
                    type="button"
                  >
                    Add {user.displayName}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : (
        <p role="status">This group has reached the limit of {MAX_ADMINS} administrators.</p>
      )}
      {message ? <p role={message.tone === "fail" ? "alert" : "status"}>{message.text}</p> : null}
    </section>
  );
}
