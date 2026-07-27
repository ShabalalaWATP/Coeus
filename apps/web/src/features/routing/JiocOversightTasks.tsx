import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { RoutingCriticStatus } from "./RoutingCriticStatus";
import { formatWorkflowState } from "../../lib/workflow/state-format";
import type { JiocOversight } from "../../lib/api-client/routing";

type InterventionAction = "hold" | "resume" | "send_to_review";
type OversightFilter = "attention" | "all" | "agent_routed" | "on_hold";

export function JiocOversightTasks({
  isError,
  isPending,
  onIntervene,
  tasks,
}: {
  isError: boolean;
  isPending: boolean;
  onIntervene: (
    ticketId: string,
    action: InterventionAction,
    reason: string,
    expectedUpdatedAt: string,
  ) => void;
  tasks: JiocOversight["tasks"];
}) {
  const [filter, setFilter] = useState<OversightFilter>("attention");
  const visibleTasks = useMemo(
    () => tasks.filter((task) => matchesFilter(task, filter)),
    [filter, tasks],
  );

  return (
    <section className="surface oversight-section" aria-labelledby="oversight-tasks-title">
      <div className="section-heading">
        <div>
          <h2 id="oversight-tasks-title">Task ownership and routing attention</h2>
          <p>
            Agent decisions and critic results are evidence. Human interventions use separate,
            audited controls.
          </p>
        </div>
        <label>
          View
          <select
            aria-label="Filter oversight tasks"
            onChange={(event) => setFilter(event.target.value as OversightFilter)}
            value={filter}
          >
            <option value="attention">Needs attention</option>
            <option value="all">All recent tasks</option>
            <option value="agent_routed">Agent-routed</option>
            <option value="on_hold">On hold</option>
          </select>
        </label>
      </div>
      {isError ? (
        <p className="auth-error" role="alert">
          The intervention could not be applied. Refresh the oversight view and try again.
        </p>
      ) : null}
      {visibleTasks.length === 0 ? (
        <p>No tasks match this view.</p>
      ) : (
        <div className="oversight-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Reference</th>
                <th>State</th>
                <th>Current route</th>
                <th>Team</th>
                <th>Work</th>
                <th>JIOC Agent decision</th>
                <th>Routing critic</th>
                <th>Intervention</th>
              </tr>
            </thead>
            <tbody>
              {visibleTasks.map((task) => (
                <tr key={task.ticketId}>
                  <th>
                    {["JIOC_REVIEW", "JIOC_REANALYSIS_ADJUDICATION"].includes(task.state) ? (
                      <Link to={`/jioc/queue?ticket=${task.ticketId}`}>{task.reference}</Link>
                    ) : (
                      task.reference
                    )}
                  </th>
                  <td>{formatWorkflowState(task.state)}</td>
                  <td>{task.route?.toUpperCase() ?? "Unrouted"}</td>
                  <td>{task.teamName ?? "Unassigned"}</td>
                  <td>
                    {task.analystCount} analysts
                    <br />
                    {task.completedWorkPackageCount} of {task.workPackageCount} packages
                  </td>
                  <td>
                    <AgentDecision task={task} />
                  </td>
                  <td>
                    <RoutingCriticStatus task={task} />
                  </td>
                  <td>
                    <TaskInterventionControls
                      disabled={isPending}
                      onIntervene={(action, reason) =>
                        onIntervene(task.ticketId, action, reason, task.updatedAt)
                      }
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

function AgentDecision({ task }: { task: JiocOversight["tasks"][number] }) {
  if (!task.agentDisposition) return <span>Legacy or pending</span>;
  return (
    <dl aria-label={`JIOC Agent decision for ${task.reference}`}>
      <div>
        <dt>Outcome</dt>
        <dd>{formatAgentDisposition(task.agentDisposition)}</dd>
      </div>
      <div>
        <dt>Recommended route</dt>
        <dd>{task.agentRoute?.toUpperCase() ?? "None"}</dd>
      </div>
      <div>
        <dt>Policy</dt>
        <dd>{task.agentPolicyVersion ?? "Unknown"}</dd>
      </div>
      <div>
        <dt>Evidence score</dt>
        <dd>
          {task.agentConfidence?.toFixed(2) ?? "Unknown"} <small>Not a probability</small>
        </dd>
      </div>
      <div>
        <dt>Reasons</dt>
        <dd>
          {task.agentRationaleCodes.length
            ? task.agentRationaleCodes.map(formatCode).join(", ")
            : "None recorded"}
        </dd>
      </div>
    </dl>
  );
}

function TaskInterventionControls({
  disabled,
  onIntervene,
  state,
}: {
  disabled: boolean;
  onIntervene: (action: InterventionAction, reason: string) => void;
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
        aria-label={`Intervention reason for ${state}`}
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

function matchesFilter(task: JiocOversight["tasks"][number], filter: OversightFilter) {
  if (filter === "all") return true;
  if (filter === "agent_routed") return task.agentDisposition === "auto_applied";
  if (filter === "on_hold") return task.state === "JIOC_INTERVENTION_HOLD";
  return (
    [
      "JIOC_ROUTING_PENDING",
      "JIOC_REVIEW",
      "JIOC_REANALYSIS_ADJUDICATION",
      "JIOC_INTERVENTION_HOLD",
    ].includes(task.state) ||
    task.agentDisposition === "manager_review" ||
    task.criticChallengeCount > 0 ||
    task.criticMissingEvidenceCount > 0
  );
}

function formatCode(value: string) {
  return value.replaceAll("_", " ");
}

function formatAgentDisposition(value: string) {
  return value === "manager_review" ? "Human JIOC review" : formatCode(value);
}
