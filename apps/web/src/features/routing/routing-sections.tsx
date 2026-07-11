import { Bot } from "lucide-react";

import type {
  CmCapabilityReview,
  RfaCapabilityReview,
  RoutingQueue,
  RoutingTicket,
} from "../../lib/api-client/routing";
import { formatTaggedReason } from "./routing-labels";

function AgentChip({ label }: { label: string }) {
  return (
    <span className="agent-chip">
      <Bot aria-hidden="true" size={13} />
      {label}
    </span>
  );
}

export function RoutingStats({ queue }: { queue: RoutingQueue }) {
  return (
    <dl className="routing-stats" aria-label="Routing statistics">
      <div>
        <dt>JIOC review</dt>
        <dd>{queue.stats.jiocQueueCount}</dd>
      </div>
      <div>
        <dt>Collect choice</dt>
        <dd>{queue.stats.collectChoiceCount}</dd>
      </div>
      <div>
        <dt>CM fallback</dt>
        <dd>{Math.round(queue.stats.cmFallbackRate * 100)}%</dd>
      </div>
    </dl>
  );
}

export function Recommendation({ ticket }: { ticket: RoutingTicket }) {
  return ticket.recommendation ? (
    <article className="routing-recommendation">
      <AgentChip label="Orchestrator agent" />
      <h3>Recommended route: {ticket.recommendation.recommendedRoute.toUpperCase()}</h3>
      <p>{ticket.recommendation.reasoningSummary}</p>
    </article>
  ) : (
    <article className="routing-recommendation">
      <AgentChip label="Orchestrator agent" />
      <h3>No route recommendation</h3>
      <p>Capability checks have not run for this ticket.</p>
    </article>
  );
}

export function Review({
  review,
  title,
}: {
  review: CmCapabilityReview | RfaCapabilityReview | null;
  title: string;
}) {
  if (!review) {
    return null;
  }
  return (
    <article className="routing-review">
      <AgentChip label="Capability agent" />
      <h3>{title}</h3>
      <p>{review.reasoningSummary}</p>
      <dl>
        <div>
          <dt>Can satisfy</dt>
          <dd>{review.canSatisfy ? "Yes" : "No"}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{Math.round(review.confidence * 100)}%</dd>
        </div>
        <div>
          <dt>Effort</dt>
          <dd>{review.estimatedEffort}</dd>
        </div>
        <div>
          <dt>Team</dt>
          <dd>{reviewTeamName(review) ?? "No team matched"}</dd>
        </div>
      </dl>
      {review.requiredClarifications.length ? (
        <ul>
          {review.requiredClarifications.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
      {review.candidateTeams?.length ? (
        <div className="routing-candidates">
          <h4>Candidate teams</h4>
          <ol>
            {review.candidateTeams.map((candidate) => (
              <li
                aria-label={`${candidate.name}. ${candidate.reasons.map(formatTaggedReason).join(". ")}`}
                key={candidate.teamId}
                title={candidate.reasons.map(formatTaggedReason).join(", ")}
              >
                <strong>{candidate.name}</strong>
                <span>score {candidate.score}</span>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </article>
  );
}

function reviewTeamName(review: CmCapabilityReview | RfaCapabilityReview) {
  if ("suggestedTeamName" in review) {
    return review.suggestedTeamName;
  }
  return review.suggestedCollectionTeamName;
}

export function PlanUpdates({ ticket }: { ticket: RoutingTicket }) {
  return ticket.workflowPlanUpdates.length ? (
    <article className="routing-plan">
      <h3>Workflow plan updates</h3>
      <ul>
        {ticket.workflowPlanUpdates.map((item) => (
          <li key={item.id}>
            <strong>{item.title}</strong>
            <span>{item.ownerRole}</span>
          </li>
        ))}
      </ul>
    </article>
  ) : null;
}
