import { formatTaggedReason } from "./routing-labels";
import type { RoutingTicket } from "../../lib/api-client/routing";

export function RoutingPriorityAssessment({ ticket }: { ticket: RoutingTicket }) {
  const assessment = ticket.priorityAssessment;
  if (!assessment) return null;
  return (
    <div className="priority-assessment">
      <span className={`priority-badge priority-badge--${assessment.tier.toLowerCase()}`}>
        {assessment.tier}
      </span>
      <span>Internal priority score {assessment.score}</span>
      <ul>
        {assessment.reasons.map((reason) => (
          <li key={reason}>{formatTaggedReason(reason)}</li>
        ))}
      </ul>
    </div>
  );
}
