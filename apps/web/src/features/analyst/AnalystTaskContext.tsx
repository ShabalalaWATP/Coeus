import type { AnalystTask } from "../../lib/api-client/analyst";

export function AnalystTaskContext({ task }: { task: AnalystTask }) {
  return (
    <section className="analyst-context">
      <dl>
        <div>
          <dt>State</dt>
          <dd>{task.state.replaceAll("_", " ")}</dd>
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
      </dl>
      <p>{task.description}</p>
      <ul>
        {task.managerNotes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </section>
  );
}
