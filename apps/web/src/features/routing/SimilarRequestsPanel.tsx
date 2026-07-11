import { GitCompareArrows, Link2, RefreshCw } from "lucide-react";

import type { SimilarRequestList } from "../../lib/api-client/similar-requests";
import { formatWorkflowState } from "../../lib/workflow/state-format";
import { formatTaggedReason } from "./routing-labels";

type SimilarRequestsPanelProps = {
  isLinking: boolean;
  isLoading: boolean;
  isQueryError: boolean;
  matches?: SimilarRequestList;
  onLink: (ticketId: string) => void;
  onRetry: () => void;
};

export function SimilarRequestsPanel({
  isLinking,
  isLoading,
  isQueryError,
  matches,
  onLink,
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
              <small>{formatWorkflowState(match.state)}</small>
              <div className="similar-match__reasons">
                {match.reasons.map((reason) => (
                  <span key={reason}>{formatTaggedReason(reason)}</span>
                ))}
              </div>
              <button
                disabled={match.alreadyLinked || isLinking}
                onClick={() => onLink(match.ticketId)}
                type="button"
              >
                <Link2 aria-hidden="true" size={15} />
                {match.alreadyLinked ? "Linked" : "Link as related"}
              </button>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
