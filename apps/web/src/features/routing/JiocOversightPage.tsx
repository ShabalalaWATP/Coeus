import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { JiocOversightTasks } from "./JiocOversightTasks";
import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  getJiocOversight,
  interveneInRouting,
  type JiocOversight,
} from "../../lib/api-client/routing";
import { useAuth } from "../../lib/auth/auth-context";
import { formatWorkflowState } from "../../lib/workflow/state-format";

export default function JiocOversightPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const oversightQuery = useQuery({
    queryKey: ["jioc-oversight"],
    queryFn: getJiocOversight,
    retry: false,
  });
  const oversight = oversightQuery.data;
  const intervention = useMutation({
    mutationFn: (input: {
      action: "hold" | "resume" | "send_to_review";
      reason: string;
      ticketId: string;
      expectedUpdatedAt: string;
    }) =>
      interveneInRouting(
        input.ticketId,
        input.action,
        input.reason,
        session?.csrfToken ?? "",
        input.expectedUpdatedAt,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jioc-oversight"] }),
  });

  return (
    <div className="workspace-page oversight-page">
      <section className="overview-hero" aria-labelledby="oversight-title">
        <div>
          <h1 id="oversight-title">JIOC Oversight</h1>
          <p>Monitor agent routing, team capacity and workload, and intervene when required.</p>
        </div>
      </section>
      {oversightQuery.isLoading ? <LoadingState label="Loading JIOC oversight" /> : null}
      {oversightQuery.isError ? <ErrorState onRetry={() => void oversightQuery.refetch()} /> : null}
      {oversight ? (
        <>
          <section className="oversight-counts" aria-label="Workflow totals">
            <CountGroup label="By state" counts={oversight.countsByState} formatState />
            <CountGroup label="By route" counts={oversight.countsByRoute} />
            <CountGroup label="By Agent outcome" counts={oversight.countsByAgentDisposition} />
          </section>
          <OversightTeams teams={oversight.teams} />
          <JiocOversightTasks
            isError={intervention.isError}
            isPending={intervention.isPending}
            onIntervene={(ticketId, action, reason, expectedUpdatedAt) =>
              intervention.mutate({ action, expectedUpdatedAt, reason, ticketId })
            }
            tasks={oversight.tasks}
          />
          <OversightAnalysts analysts={oversight.analysts} />
        </>
      ) : null}
    </div>
  );
}

function CountGroup({
  counts,
  formatState = false,
  label,
}: {
  counts: { key: string; count: number }[];
  formatState?: boolean;
  label: string;
}) {
  return (
    <section className="surface oversight-count-group">
      <h2>{label}</h2>
      <dl>
        {counts.map((item) => (
          <div key={item.key}>
            <dt>{formatState ? formatWorkflowState(item.key) : item.key.toUpperCase()}</dt>
            <dd>{item.count}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function OversightTeams({ teams }: { teams: JiocOversight["teams"] }) {
  return (
    <section className="surface oversight-section" aria-labelledby="oversight-teams-title">
      <h2 id="oversight-teams-title">Area teams</h2>
      <div className="oversight-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Team</th>
              <th>Area</th>
              <th>Available</th>
              <th>Live tasks</th>
            </tr>
          </thead>
          <tbody>
            {teams.map((team) => (
              <tr key={team.teamId}>
                <th>{team.name}</th>
                <td>{team.kind.toUpperCase()}</td>
                <td>
                  {team.availableMembers} of {team.activeMembers}
                </td>
                <td>{team.liveTaskCount}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function OversightAnalysts({ analysts }: { analysts: JiocOversight["analysts"] }) {
  return (
    <section className="surface oversight-section" aria-labelledby="oversight-analysts-title">
      <h2 id="oversight-analysts-title">Analyst workload</h2>
      {analysts.length === 0 ? (
        <p>No analysts are allocated.</p>
      ) : (
        <ul className="oversight-analysts">
          {analysts.map((analyst) => (
            <li key={analyst.userId}>
              <strong>{analyst.displayName}</strong>
              <span>
                {analyst.liveTaskCount} live {analyst.liveTaskCount === 1 ? "task" : "tasks"}
              </span>
              <small>
                {analyst.teamIds.length} {analyst.teamIds.length === 1 ? "team" : "teams"}
              </small>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
