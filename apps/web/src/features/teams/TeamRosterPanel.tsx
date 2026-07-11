import { useMutation, useQueryClient } from "@tanstack/react-query";
import { UserMinus, UserPlus } from "lucide-react";
import { useState } from "react";

import { addTeamMember, removeTeamMember, type OrgTeam } from "../../lib/api-client/teams";
import { listUserDirectory } from "../../lib/api-client/tickets";
import { useActionError } from "../../lib/mutations/action-error";

type TeamRosterPanelProps = {
  csrfToken: string;
  currentUserId: string;
  team: OrgTeam;
};

export function TeamRosterPanel({ csrfToken, currentUserId, team }: TeamRosterPanelProps) {
  const queryClient = useQueryClient();
  const [newMemberName, setNewMemberName] = useState("");
  const { actionError, clearActionError, failActionWith } = useActionError();
  const isManager = team.members.some(
    (member) => member.userId === currentUserId && member.isManager,
  );
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["teams"] });
  const addMutation = useMutation({
    mutationFn: async () => {
      const directory = await listUserDirectory(newMemberName.trim());
      const match = directory.find(
        (user) => user.username.toLowerCase() === newMemberName.trim().toLowerCase(),
      );
      if (!match) {
        throw new Error("No user with that username was found.");
      }
      return addTeamMember(team.id, match.id, csrfToken);
    },
    onError: failActionWith("The member could not be added. Check the username."),
    onMutate: clearActionError,
    onSuccess: () => {
      setNewMemberName("");
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
        <form
          className="team-roster__add"
          onSubmit={(event) => {
            event.preventDefault();
            addMutation.mutate();
          }}
        >
          <label>
            Add member by username
            <input
              onChange={(event) => setNewMemberName(event.target.value)}
              placeholder="analyst@example.test"
              value={newMemberName}
            />
          </label>
          <button disabled={newMemberName.trim().length < 3 || addMutation.isPending} type="submit">
            <UserPlus aria-hidden="true" size={16} />
            Add member
          </button>
        </form>
      ) : null}
      {actionError ? (
        <p className="auth-error" role="alert">
          {actionError}
        </p>
      ) : null}
    </section>
  );
}
