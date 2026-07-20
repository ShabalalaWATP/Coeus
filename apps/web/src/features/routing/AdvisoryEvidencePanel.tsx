import type { AdvisoryAgentKind, AdvisoryAgentRun } from "../../lib/api-client/routing";

const agentLabels: Record<AdvisoryAgentKind, string> = {
  intake_planner: "Intake planner",
  search_planner: "Search planner",
  routing_critic: "Routing critic",
};

export function AdvisoryEvidencePanel({ runs }: { runs: AdvisoryAgentRun[] }) {
  if (runs.length === 0) return null;
  return (
    <section className="workspace-details" aria-labelledby="advisory-evidence-title">
      <h3 id="advisory-evidence-title">Bounded agent advice</h3>
      <p>
        These suggestions are decision context for staff. Deterministic controllers retain every
        permission, workflow and assurance decision.
      </p>
      {runs.map((run) => (
        <article key={run.id} aria-label={agentLabels[run.advice.agent]}>
          <h4>{agentLabels[run.advice.agent]}</h4>
          <p>
            Outcome: {formatCode(run.advice.outcome)}
            {run.advice.verdict ? ` · Verdict: ${formatCode(run.advice.verdict)}` : ""}
          </p>
          {run.advice.agent === "routing_critic" ? (
            <p className="workspace-alert" role="note">
              Advisory evidence only. The routing critic is shadow-only and cannot route or change
              workflow.
            </p>
          ) : null}
          {run.advice.items.length > 0 ? (
            <ul>
              {run.advice.items.map((item) => (
                <li key={`${item.kind}:${item.code}`}>
                  <strong>{formatCode(item.kind)}:</strong> {item.detail}
                </li>
              ))}
            </ul>
          ) : (
            <p>No issues or suggestions were recorded.</p>
          )}
        </article>
      ))}
    </section>
  );
}

function formatCode(value: string) {
  return value.replaceAll("_", " ");
}
