import { useQuery } from "@tanstack/react-query";

import { ErrorState, LoadingState } from "../../components/ui/PageState";
import { getJiocOversight, type JiocOversight } from "../../lib/api-client/routing";
import { formatWorkflowState } from "../../lib/workflow/state-format";

export default function JiocOversightPage() {
  const oversightQuery = useQuery({
    queryKey: ["jioc-oversight"],
    queryFn: getJiocOversight,
    retry: false,
  });
  const oversight = oversightQuery.data;

  return (
    <div className="workspace-page oversight-page">
      <section className="overview-hero" aria-labelledby="oversight-title">
        <div>
          <h1 id="oversight-title">JIOC Oversight</h1>
          <p>Read-only task ownership, team capacity and analyst workload across the workflow.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>
      {oversightQuery.isLoading ? <LoadingState label="Loading JIOC oversight" /> : null}
      {oversightQuery.isError ? <ErrorState onRetry={() => void oversightQuery.refetch()} /> : null}
      {oversight ? (
        <>
          <section className="oversight-counts" aria-label="Workflow totals">
            <CountGroup label="By state" counts={oversight.countsByState} formatState />
            <CountGroup label="By route" counts={oversight.countsByRoute} />
          </section>
          <OversightTeams teams={oversight.teams} />
          <OversightTasks tasks={oversight.tasks} />
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

function OversightTasks({ tasks }: { tasks: JiocOversight["tasks"] }) {
  return (
    <section className="surface oversight-section" aria-labelledby="oversight-tasks-title">
      <h2 id="oversight-tasks-title">Task ownership</h2>
      {tasks.length === 0 ? (
        <p>No active tasks.</p>
      ) : (
        <div className="oversight-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Reference</th>
                <th>State</th>
                <th>Route</th>
                <th>Team</th>
                <th>Analysts</th>
                <th>Work packages</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.ticketId}>
                  <th>{task.reference}</th>
                  <td>{formatWorkflowState(task.state)}</td>
                  <td>{task.route?.toUpperCase() ?? "Unrouted"}</td>
                  <td>{task.teamName ?? "Unassigned"}</td>
                  <td>{task.analystCount}</td>
                  <td>
                    {task.completedWorkPackageCount} of {task.workPackageCount}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
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
