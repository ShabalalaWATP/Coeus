import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { RoutingCriticStatus } from "./RoutingCriticStatus";
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
    }) => interveneInRouting(input.ticketId, input.action, input.reason, session?.csrfToken ?? ""),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jioc-oversight"] }),
  });

  return (
    <div className="workspace-page oversight-page">
      <section className="overview-hero" aria-labelledby="oversight-title">
        <div>
          <h1 id="oversight-title">JIOC Oversight</h1>
          <p>Monitor agent routing, team capacity and workload, and intervene when required.</p>
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
          <OversightTasks
            isPending={intervention.isPending}
            onIntervene={(ticketId, action, reason) =>
              intervention.mutate({ action, reason, ticketId })
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

function OversightTasks({
  isPending,
  onIntervene,
  tasks,
}: {
  isPending: boolean;
  onIntervene: (
    ticketId: string,
    action: "hold" | "resume" | "send_to_review",
    reason: string,
  ) => void;
  tasks: JiocOversight["tasks"];
}) {
  return (
    <section className="surface oversight-section" aria-labelledby="oversight-tasks-title">
      <h2 id="oversight-tasks-title">Task ownership</h2>
      <p className="workspace-alert" role="note">
        Routing critic results are advisory evidence only. The shadow-only critic cannot route or
        change workflow. JIOC managers monitor its challenges and intervene through the separate
        controls below.
      </p>
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
                <th>Agent decision</th>
                <th>Routing critic</th>
                <th>Intervention</th>
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
                  <td>
                    {task.agentDisposition
                      ? `${task.agentDisposition.replaceAll("_", " ")} (${Math.round(
                          (task.agentConfidence ?? 0) * 100,
                        )}%)`
                      : "Legacy or pending"}
                  </td>
                  <td>
                    <RoutingCriticStatus task={task} />
                  </td>
                  <td>
                    <TaskInterventionControls
                      disabled={isPending}
                      onIntervene={(action, reason) => onIntervene(task.ticketId, action, reason)}
                      state={task.state}
                    />
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

function TaskInterventionControls({
  disabled,
  onIntervene,
  state,
}: {
  disabled: boolean;
  onIntervene: (action: "hold" | "resume" | "send_to_review", reason: string) => void;
  state: string;
}) {
  const [reason, setReason] = useState("");
  const ready = reason.trim().length >= 3 && !disabled;
  const onHold = state === "JIOC_INTERVENTION_HOLD";
  const canReview = ["JIOC_ROUTING_PENDING", "COLLECT_CHOICE", "ANALYST_ASSIGNMENT"].includes(
    state,
  );
  const canHold = [
    "JIOC_ROUTING_PENDING",
    "JIOC_REVIEW",
    "COLLECT_CHOICE",
    "ANALYST_ASSIGNMENT",
    "ANALYST_IN_PROGRESS",
    "MANAGER_APPROVAL",
    "QC_REVIEW",
    "REWORK_REQUIRED",
  ].includes(state);
  if (!onHold && !canReview && !canHold) return <span>No action available</span>;
  return (
    <div className="oversight-intervention">
      <input
        aria-label="Intervention reason"
        onChange={(event) => setReason(event.target.value)}
        placeholder="Reason required"
        value={reason}
      />
      {onHold ? (
        <button disabled={!ready} onClick={() => onIntervene("resume", reason)} type="button">
          Resume
        </button>
      ) : (
        <>
          <button disabled={!ready} onClick={() => onIntervene("hold", reason)} type="button">
            Hold
          </button>
          {canReview ? (
            <button
              disabled={!ready}
              onClick={() => onIntervene("send_to_review", reason)}
              type="button"
            >
              Send to review
            </button>
          ) : null}
        </>
      )}
    </div>
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
