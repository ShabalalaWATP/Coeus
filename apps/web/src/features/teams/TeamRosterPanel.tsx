import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserMinus, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";

import {
  addTeamMember,
  listTeamMemberCandidates,
  removeTeamMember,
  type OrgTeam,
} from "../../lib/api-client/teams";
import { useActionError } from "../../lib/mutations/action-error";

const SEARCH_MIN_LENGTH = 3;
const SEARCH_DEBOUNCE_MS = 250;

type TeamRosterPanelProps = {
  csrfToken: string;
  currentUserId: string;
  team: OrgTeam;
};

function useDebouncedValue(value: string, delayMs: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export function TeamRosterPanel({ csrfToken, currentUserId, team }: TeamRosterPanelProps) {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState("");
  const { actionError, clearActionError, failActionWith } = useActionError();
  const isManager = team.members.some(
    (member) => member.userId === currentUserId && member.isManager,
  );
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["teams"] });
  const debouncedTerm = useDebouncedValue(searchTerm.trim(), SEARCH_DEBOUNCE_MS);
  const canSearch = isManager && debouncedTerm.length >= SEARCH_MIN_LENGTH;
  const directoryQuery = useQuery({
    enabled: canSearch,
    queryFn: () => listTeamMemberCandidates(team.id, debouncedTerm),
    queryKey: ["teams", "directory", debouncedTerm],
  });
  const memberIds = new Set(team.members.map((member) => member.userId));
  const suggestions = (directoryQuery.data?.users ?? []).filter(
    (user) => !memberIds.has(user.userId),
  );
  const addMutation = useMutation({
    mutationFn: (userId: string) => addTeamMember(team.id, userId, csrfToken),
    onError: failActionWith("The member could not be added."),
    onMutate: clearActionError,
    onSuccess: () => {
      setSearchTerm("");
      refresh();
    },
  });
  const removeMutation = useMutation({
    mutationFn: (userId: string) => removeTeamMember(team.id, userId, csrfToken),
    onError: failActionWith("The member could not be removed."),
    onMutate: clearActionError,
    onSuccess: refresh,
  });

  return (
    <section className="surface team-roster" aria-label="Team roster">
      <h2>{team.name}</h2>
      <ul className="team-roster__list">
        {team.members.map((member) => (
          <li key={member.userId}>
            <div>
              <strong>{member.displayName}</strong>
              {member.isManager ? <span className="team-roster__badge">Manager</span> : null}
              <p>{member.title || member.username}</p>
              {member.specialisms.length > 0 ? (
                <small>{member.specialisms.join(", ")}</small>
              ) : null}
              {member.bio ? <p className="team-roster__bio">{member.bio}</p> : null}
            </div>
            {isManager && !member.isManager ? (
              <button
                aria-label={`Remove ${member.displayName}`}
                disabled={removeMutation.isPending}
                onClick={() => removeMutation.mutate(member.userId)}
                type="button"
              >
                <UserMinus aria-hidden="true" size={16} />
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      {isManager ? (
        <div className="team-roster__add">
          <label>
            Add member
            <input
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search by name or username"
              value={searchTerm}
            />
          </label>
          {canSearch && suggestions.length > 0 ? (
            <ul aria-label="Matching users" className="team-roster__suggestions">
              {suggestions.map((user) => (
                <li key={user.userId}>
                  <button
                    disabled={addMutation.isPending}
                    onClick={() => addMutation.mutate(user.userId)}
                    type="button"
                  >
                    <UserPlus aria-hidden="true" size={16} />
                    <span>
                      <strong>{user.displayName}</strong>
                      <small>{user.title || user.username}</small>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {canSearch && directoryQuery.isSuccess && suggestions.length === 0 ? (
            <p className="team-roster__hint">No matching users found.</p>
          ) : null}
        </div>
      ) : null}
      {actionError ? (
        <p className="auth-error" role="alert">
          {actionError}
        </p>
      ) : null}
    </section>
  );
}
