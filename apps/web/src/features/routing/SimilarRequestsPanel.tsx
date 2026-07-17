import { GitCompareArrows, Link2, RefreshCw, XCircle } from "lucide-react";

import type { SimilarRequestList } from "../../lib/api-client/similar-requests";
import { formatWorkflowState } from "../../lib/workflow/state-format";
import { formatTaggedReason } from "./routing-labels";

type SimilarRequestsPanelProps = {
  isMutating: boolean;
  isLoading: boolean;
  isQueryError: boolean;
  matches?: SimilarRequestList;
  onLink: (ticketId: string) => void;
  onMarkDuplicate: (ticketId: string, withdrawSource: boolean) => void;
  onRetry: () => void;
};

export function SimilarRequestsPanel({
  isMutating,
  isLoading,
  isQueryError,
  matches,
  onLink,
  onMarkDuplicate,
  onRetry,
}: SimilarRequestsPanelProps) {
  const items = matches?.matches ?? [];

  return (
    <section className="routing-similar" aria-labelledby="routing-similar-title">
      <div className="section-heading access-heading">
        <GitCompareArrows aria-hidden="true" size={20} />
        <h3 id="routing-similar-title">Similar open requests</h3>
      </div>
      {isLoading ? <p>Checking open requests</p> : null}
      {isQueryError ? (
        <div className="routing-similar__error" role="alert">
          <span>Similar requests could not be loaded.</span>
          <button onClick={onRetry} type="button">
            <RefreshCw aria-hidden="true" size={15} />
            Retry
          </button>
        </div>
      ) : null}
      {!isLoading && !isQueryError && items.length === 0 ? <p>No similar open requests.</p> : null}
      {items.length ? (
        <div className="routing-similar__list">
          {items.map((match) => (
            <article className="routing-similar__item" key={match.ticketId}>
              <div>
                <strong>{match.reference}</strong>
                <span>{match.title}</span>
              </div>
              <span className="similar-score">{Math.round(match.score * 100)}%</span>
              <small>
                {match.requestKind} · {formatWorkflowState(match.state)}
              </small>
              <div className="routing-similar__context">
                {match.approvedRoute ? (
                  <span>Route: {match.approvedRoute.toUpperCase()}</span>
                ) : null}
                {match.assignedTeam ? <span>Team: {match.assignedTeam}</span> : null}
                {match.requestingUnit ? <span>Unit: {match.requestingUnit}</span> : null}
                {match.supportedOperation ? (
                  <span>Operation: {match.supportedOperation}</span>
                ) : null}
                {match.timePeriodStart || match.timePeriodEnd ? (
                  <span>
                    Window: {match.timePeriodStart ?? "open"} to {match.timePeriodEnd ?? "open"}
                  </span>
                ) : null}
              </div>
              <div className="similar-match__reasons">
                {match.reasons.map((reason) => (
                  <span key={reason}>{formatTaggedReason(reason)}</span>
                ))}
              </div>
              <div className="routing-similar__actions">
                <button
                  disabled={match.alreadyLinked || isMutating}
                  onClick={() => onLink(match.ticketId)}
                  type="button"
                >
                  <Link2 aria-hidden="true" size={15} />
                  {match.alreadyLinked ? "Linked" : "Link as related"}
                </button>
                <button
                  disabled={match.alreadyMarkedDuplicate || isMutating}
                  onClick={() => onMarkDuplicate(match.ticketId, false)}
                  type="button"
                >
                  <XCircle aria-hidden="true" size={15} />
                  {match.alreadyMarkedDuplicate ? "Duplicate marked" : "Mark duplicate"}
                </button>
                <button
                  className="routing-similar__withdraw"
                  disabled={match.alreadyMarkedDuplicate || isMutating}
                  onClick={() => {
                    if (
                      window.confirm("Mark this source request as a duplicate and withdraw it?")
                    ) {
                      onMarkDuplicate(match.ticketId, true);
                    }
                  }}
                  type="button"
                >
                  <XCircle aria-hidden="true" size={15} /> Mark &amp; withdraw source
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
