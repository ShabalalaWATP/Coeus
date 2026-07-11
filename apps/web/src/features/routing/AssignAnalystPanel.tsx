import { useMutation, useQuery } from "@tanstack/react-query";
import { UserCheck } from "lucide-react";
import { useState } from "react";

import {
  assignAnalystTask,
  listAnalystCandidates,
  type AnalystTask,
} from "../../lib/api-client/analyst";
import { listTeams, teamAvailability } from "../../lib/api-client/teams";
import type { RoutingRoute } from "../../lib/api-client/routing";

const MAX_ANALYSTS = 5;

type AssignAnalystPanelProps = {
  csrfToken: string;
  onAssigned: (task: AnalystTask) => void;
  route?: RoutingRoute;
  suggestedTeamName?: string | null;
  ticketId: string;
};

export function AssignAnalystPanel({
  csrfToken,
  onAssigned,
  route,
  suggestedTeamName,
  ticketId,
}: AssignAnalystPanelProps) {
  const [analystUserIds, setAnalystUserIds] = useState<string[]>([]);
  const [teamName, setTeamName] = useState(suggestedTeamName ?? "");
  const [workPackages, setWorkPackages] = useState("");
  const candidatesQuery = useQuery({
    queryKey: ["analyst-candidates"],
    queryFn: listAnalystCandidates,
  });
  const teamsQuery = useQuery({ queryKey: ["teams"], queryFn: listTeams });
  const orgTeam = (teamsQuery.data?.teams ?? []).find(
    (team) => team.kind === (route === "cm" ? "cm" : "rfa"),
  );
  const availabilityQuery = useQuery({
    enabled: orgTeam !== undefined,
    queryKey: ["team-availability", orgTeam?.id],
    queryFn: () => teamAvailability(orgTeam?.id ?? "", new Date().toISOString().slice(0, 10)),
  });
  const assignMutation = useMutation({
    mutationFn: () =>
      assignAnalystTask(
        ticketId,
        analystUserIds,
        teamName.trim(),
        packageTitles(workPackages),
        csrfToken,
      ),
    onSuccess: (task) => onAssigned(task),
  });
  const candidates = candidatesQuery.data?.analysts ?? [];
  const toggleAnalyst = (userId: string, checked: boolean) => {
    setAnalystUserIds((current) =>
      checked ? [...current, userId] : current.filter((id) => id !== userId),
    );
  };

  return (
    <section className="routing-assign" aria-label="Assign analysts">
      <h3>Assign analysts</h3>
      <p>
        The route is approved. Choose up to {MAX_ANALYSTS} analysts to start production. Work
        packages default to the approved route plan when left blank.
      </p>
      {availabilityQuery.data ? (
        <p className="routing-assign__availability">
          {availabilityQuery.data.free} of {availabilityQuery.data.members} team members are free
          today ({availabilityQuery.data.assignedLive} on live tasks,{" "}
          {availabilityQuery.data.onLeave} on leave).
        </p>
      ) : null}
      {candidatesQuery.isError ? (
        <p role="alert">Analyst candidates could not be loaded. Refresh to try again.</p>
      ) : null}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          assignMutation.mutate();
        }}
      >
        <fieldset className="routing-assign__analysts">
          <legend>Analysts</legend>
          {candidates.map((candidate) => (
            <label key={candidate.userId}>
              <input
                checked={analystUserIds.includes(candidate.userId)}
                disabled={
                  !analystUserIds.includes(candidate.userId) &&
                  analystUserIds.length >= MAX_ANALYSTS
                }
                onChange={(event) => toggleAnalyst(candidate.userId, event.target.checked)}
                type="checkbox"
              />
              {candidate.displayName}
            </label>
          ))}
        </fieldset>
        <label>
          Team name
          <input
            onChange={(event) => setTeamName(event.target.value)}
            placeholder="Analyst or capability team"
            value={teamName}
          />
        </label>
        <label>
          Work packages (semicolon separated)
          <input
            onChange={(event) => setWorkPackages(event.target.value)}
            placeholder="Optional"
            value={workPackages}
          />
        </label>
        <button disabled={analystUserIds.length === 0 || assignMutation.isPending} type="submit">
          <UserCheck aria-hidden="true" size={18} />
          Assign analysts
        </button>
      </form>
      {assignMutation.isError ? (
        <p role="alert">Assignment failed. Confirm the ticket is still awaiting assignment.</p>
      ) : null}
    </section>
  );
}

function packageTitles(raw: string) {
  return raw
    .split(";")
    .map((title) => title.trim())
    .filter((title) => title !== "");
}
