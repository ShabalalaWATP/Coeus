import type {
  CmCapabilityReview,
  RfaCapabilityReview,
  RoutingQueue,
  RoutingTicket,
} from "../../lib/api-client/routing";

export function RoutingStats({ queue }: { queue: RoutingQueue }) {
  return (
    <dl className="routing-stats" aria-label="Routing statistics">
      <div>
        <dt>RFA review</dt>
        <dd>{queue.stats.rfaReviewCount}</dd>
      </div>
      <div>
        <dt>CM review</dt>
        <dd>{queue.stats.cmReviewCount}</dd>
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
      <h3>Recommended route: {ticket.recommendation.recommendedRoute.toUpperCase()}</h3>
      <p>{ticket.recommendation.reasoningSummary}</p>
    </article>
  ) : (
    <article className="routing-recommendation">
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
      </dl>
      {review.requiredClarifications.length ? (
        <ul>
          {review.requiredClarifications.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

export function PlanUpdates({ ticket }: { ticket: RoutingTicket }) {
  return ticket.projectPlanUpdates.length ? (
    <article className="routing-plan">
      <h3>Project plan updates</h3>
      <ul>
        {ticket.projectPlanUpdates.map((item) => (
          <li key={item.id}>
            <strong>{item.title}</strong>
            <span>{item.ownerRole}</span>
          </li>
        ))}
      </ul>
    </article>
  ) : null;
}
