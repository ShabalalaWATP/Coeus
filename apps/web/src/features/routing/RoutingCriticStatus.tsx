import type { JiocOversight } from "../../lib/api-client/routing";

type CriticTask = JiocOversight["tasks"][number];

export function RoutingCriticStatus({ task }: { task: CriticTask }) {
  if (!task.criticOutcome) return <span>Not yet available</span>;
  return (
    <dl aria-label={`Routing critic evidence for ${task.reference}`}>
      <div>
        <dt>Outcome</dt>
        <dd>{formatCode(task.criticOutcome)}</dd>
      </div>
      <div>
        <dt>Verdict</dt>
        <dd>{task.criticVerdict ? formatCode(task.criticVerdict) : "No verdict"}</dd>
      </div>
      <div>
        <dt>Challenges</dt>
        <dd>{task.criticChallengeCount}</dd>
      </div>
      <div>
        <dt>Missing evidence</dt>
        <dd>{task.criticMissingEvidenceCount}</dd>
      </div>
    </dl>
  );
}

function formatCode(value: string) {
  return value.replaceAll("_", " ");
}
