import { useMutation, useQuery } from "@tanstack/react-query";
import { UserCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  assignAnalystTask,
  getAssignmentTeamAvailability,
  listAnalystCandidates,
  listAssignmentTeams,
  type AnalystTask,
} from "../../lib/api-client/analyst";
import { ApiError } from "../../lib/api-client/client";
import type { RoutingRoute } from "../../lib/api-client/routing";
import { queryKeys } from "../../lib/query-keys";
import { utcAssignmentDate } from "./assignment-date";
import { AssignmentRecommendationPanel } from "./AssignmentRecommendationPanel";

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
  const [teamId, setTeamId] = useState("");
  const [workPackages, setWorkPackages] = useState("");
  const areaRoute = route ?? "rfa";
  const teamsQuery = useQuery({
    queryKey: ["assignment-teams", areaRoute],
    queryFn: () => listAssignmentTeams(areaRoute),
  });
  const availableTeams = useMemo(() => teamsQuery.data ?? [], [teamsQuery.data]);
  const selectedTeam = availableTeams.find((team) => team.teamId === teamId);
  const today = utcAssignmentDate();
  useEffect(() => {
    if (teamId || availableTeams.length === 0) return;
    const suggested = availableTeams.find((team) => team.name === suggestedTeamName);
    setTeamId(suggested?.teamId ?? (availableTeams.length === 1 ? availableTeams[0].teamId : ""));
  }, [availableTeams, suggestedTeamName, teamId]);
  const candidatesQuery = useQuery({
    enabled: teamId !== "",
    queryKey: ["analyst-candidates", areaRoute, teamId],
    queryFn: () => listAnalystCandidates(areaRoute, teamId),
  });
  const availabilityQuery = useQuery({
    enabled: selectedTeam !== undefined,
    queryKey: queryKeys.routing.assignmentAvailability(
      areaRoute,
      selectedTeam?.teamId ?? "",
      today,
    ),
    queryFn: () => getAssignmentTeamAvailability(areaRoute, selectedTeam?.teamId ?? "", today),
  });
  const assignMutation = useMutation({
    mutationFn: () =>
      assignAnalystTask(ticketId, analystUserIds, teamId, packageTitles(workPackages), csrfToken),
    onSuccess: (task) => onAssigned(task),
    onError: (error) => {
      if (error instanceof ApiError && error.code === "analyst_unavailable") {
        setAnalystUserIds([]);
        void candidatesQuery.refetch();
        void availabilityQuery.refetch();
      }
    },
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
        Select one of the teams you directly manage to own this task, then choose up to{" "}
        {MAX_ANALYSTS}
        of its analysts. Work packages default to the approved route plan when left blank.
      </p>
      {teamsQuery.isLoading ? <p role="status">Loading area teams…</p> : null}
      {teamsQuery.isError ? (
        <p role="alert">Area teams could not be loaded. Refresh to try again.</p>
      ) : null}
      {availabilityQuery.data ? (
        <p className="routing-assign__availability">
          {availabilityQuery.data.free} of {availabilityQuery.data.assignable} assignable analysts
          are free today. Total roster: {availabilityQuery.data.members} (
          {availabilityQuery.data.assignedLive} on live tasks, {availabilityQuery.data.onLeave} on
          leave).
        </p>
      ) : null}
      {teamId && candidatesQuery.isLoading ? <p role="status">Loading team analysts…</p> : null}
      {teamId && candidatesQuery.isError ? (
        <p role="alert">Analyst candidates could not be loaded. Refresh to try again.</p>
      ) : null}
      {availabilityQuery.isError ? (
        <p role="alert">Team availability could not be loaded. Refresh to try again.</p>
      ) : null}
      <AssignmentRecommendationPanel
        csrfToken={csrfToken}
        onAssigned={onAssigned}
        teamId={teamId}
        ticketId={ticketId}
      />
      <form
        onSubmit={(event) => {
          event.preventDefault();
          assignMutation.mutate();
        }}
      >
        <label>
          Team
          <select
            disabled={assignMutation.isPending || teamsQuery.isLoading}
            onChange={(event) => {
              setTeamId(event.target.value);
              setAnalystUserIds([]);
            }}
            value={teamId}
          >
            <option value="">Select a team</option>
            {availableTeams.map((team) => (
              <option key={team.teamId} value={team.teamId}>
                {team.name}
                {suggestedTeamName === team.name ? " (recommended)" : ""}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="routing-assign__analysts" disabled={teamId === ""}>
          <legend>Analysts</legend>
          {candidates.map((candidate) => (
            <label key={candidate.userId}>
              <input
                checked={analystUserIds.includes(candidate.userId)}
                disabled={
                  assignMutation.isPending ||
                  (!analystUserIds.includes(candidate.userId) &&
                    analystUserIds.length >= MAX_ANALYSTS)
                }
                onChange={(event) => toggleAnalyst(candidate.userId, event.target.checked)}
                type="checkbox"
              />
              {candidate.displayName}
            </label>
          ))}
        </fieldset>
        <label>
          Work packages (one per line)
          <textarea
            disabled={assignMutation.isPending}
            onChange={(event) => setWorkPackages(event.target.value)}
            placeholder="Optional"
            value={workPackages}
          />
        </label>
        <button
          disabled={teamId === "" || analystUserIds.length === 0 || assignMutation.isPending}
          type="submit"
        >
          <UserCheck aria-hidden="true" size={18} />
          Assign analysts
        </button>
      </form>
      {assignMutation.isError ? (
        <p role="alert">{assignmentErrorMessage(assignMutation.error)}</p>
      ) : null}
    </section>
  );
}

function assignmentErrorMessage(error: Error | null) {
  if (error instanceof ApiError && error.code === "analyst_unavailable") {
    return "The selected analyst is no longer available. Choose another analyst and try again.";
  }
  if (error instanceof ApiError && error.code === "assignment_team_not_found") {
    return "You no longer manage the selected team. Refresh the queue to continue.";
  }
  return "Assignment failed. Confirm the ticket is still awaiting assignment.";
}

function packageTitles(raw: string) {
  return raw
    .split(/[;\n]/)
    .map((title) => title.trim())
    .filter((title) => title !== "");
}
