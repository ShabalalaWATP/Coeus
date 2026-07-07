import { useQuery } from "@tanstack/react-query";
import { UserPlus, UsersRound, X } from "lucide-react";
import { useState } from "react";

import { listUserDirectory, type Ticket } from "../../lib/api-client/tickets";

type CollaboratorsPanelProps = {
  isOwner: boolean;
  isPending: boolean;
  onAdd: (username: string, access: "editor" | "viewer") => void;
  onRemove: (userId: string) => void;
  ticket: Ticket;
};

export function CollaboratorsPanel({
  isOwner,
  isPending,
  onAdd,
  onRemove,
  ticket,
}: CollaboratorsPanelProps) {
  const [username, setUsername] = useState("");
  const [access, setAccess] = useState<"editor" | "viewer">("viewer");
  const [search, setSearch] = useState("");
  const trimmedSearch = search.trim();
  const canSearch = isOwner && trimmedSearch.length >= 3;
  // The directory endpoint requires a query of at least 3 characters and
  // returns at most 10 active users.
  const directoryQuery = useQuery({
    queryKey: ["user-directory", trimmedSearch],
    queryFn: () => listUserDirectory(trimmedSearch),
    enabled: canSearch,
  });
  const taggedIds = new Set(ticket.collaborators.map((collaborator) => collaborator.userId));
  const candidates = (canSearch ? (directoryQuery.data ?? []) : []).filter(
    (user) => !taggedIds.has(user.id),
  );

  return (
    <section className="surface collaborators-panel" aria-labelledby="collaborators-title">
      <div className="section-heading access-heading">
        <UsersRound aria-hidden="true" size={20} />
        <div>
          <h2 id="collaborators-title">Tagged users</h2>
          <p>Tagged users can follow this request; editors can also change it.</p>
        </div>
      </div>
      {ticket.collaborators.length === 0 ? <p>No one is tagged yet.</p> : null}
      <ul className="collaborators-list">
        {ticket.collaborators.map((collaborator) => (
          <li key={collaborator.userId}>
            <div>
              <strong>{collaborator.displayName}</strong>
              <span>{collaborator.username}</span>
            </div>
            <span className={`status-pill status-pill--${accessTone(collaborator.access)}`}>
              {collaborator.access}
            </span>
            {isOwner ? (
              <button
                aria-label={`Remove ${collaborator.displayName}`}
                disabled={isPending}
                onClick={() => onRemove(collaborator.userId)}
                type="button"
              >
                <X aria-hidden="true" size={15} />
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      {isOwner ? (
        <form
          className="collaborators-form"
          onSubmit={(event) => {
            event.preventDefault();
            onAdd(username, access);
            setUsername("");
          }}
        >
          <label>
            Search users
            <input
              onChange={(event) => {
                setSearch(event.target.value);
                setUsername("");
              }}
              placeholder="Name or username"
              value={search}
            />
          </label>
          {trimmedSearch.length > 0 && trimmedSearch.length < 3 ? (
            <small className="field-hint">Type at least 3 characters to search.</small>
          ) : null}
          {directoryQuery.isError ? (
            <p className="auth-error" role="alert">
              The user directory could not be searched. Try again.
            </p>
          ) : null}
          {canSearch && directoryQuery.isSuccess && candidates.length === 0 ? (
            <small className="field-hint">No matching users found.</small>
          ) : null}
          <label>
            Tag a user
            <select onChange={(event) => setUsername(event.target.value)} value={username}>
              <option value="">Select a user</option>
              {candidates.map((user) => (
                <option key={user.id} value={user.username}>
                  {user.displayName}
                </option>
              ))}
            </select>
          </label>
          <label>
            Access
            <select
              onChange={(event) => setAccess(event.target.value as "editor" | "viewer")}
              value={access}
            >
              <option value="viewer">Viewer</option>
              <option value="editor">Editor</option>
            </select>
          </label>
          <button disabled={username === "" || isPending} type="submit">
            <UserPlus aria-hidden="true" size={16} />
            Tag user
          </button>
        </form>
      ) : null}
    </section>
  );
}

function accessTone(access: "editor" | "viewer") {
  return access === "editor" ? "info" : "success";
}
