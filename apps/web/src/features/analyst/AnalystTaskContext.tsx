import type { AnalystTask } from "../../lib/api-client/analyst";
import { formatWorkflowState } from "../../lib/workflow/state-format";

export function AnalystTaskContext({ task }: { task: AnalystTask }) {
  return (
    <section className="analyst-context">
      <dl>
        <div>
          <dt>State</dt>
          <dd>{formatWorkflowState(task.state)}</dd>
        </div>
        <div>
          <dt>Region</dt>
          <dd>{task.areaOrRegion ?? "Not set"}</dd>
        </div>
        <div>
          <dt>Output</dt>
          <dd>{task.requiredOutputFormat ?? "Not set"}</dd>
        </div>
        <div>
          <dt>Team</dt>
          <dd>{task.assignments[0]?.teamName ?? "Not assigned"}</dd>
        </div>
        <div>
          <dt>Analysts</dt>
          <dd>{task.assignments.length} assigned</dd>
        </div>
        <div>
          <dt>Priority</dt>
          <dd className="analyst-context__capitalise">{task.priority ?? "Not set"}</dd>
        </div>
      </dl>
      <h3>Tasking question</h3>
      <p>{task.operationalQuestion ?? "No operational question was supplied."}</p>
      <h3>Background</h3>
      <p>{task.description ?? "No background description was supplied."}</p>
      {task.chatSummary.length ? (
        <>
          <h3>Requester context</h3>
          <ul>
            {task.chatSummary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      ) : null}
      {task.managerNotes.length ? (
        <>
          <h3>Manager direction</h3>
          <ul>
            {task.managerNotes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
