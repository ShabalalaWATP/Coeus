import { Eye, GitMerge, ShieldAlert } from "lucide-react";

import type { SimilarRequestNotice } from "../../lib/api-client/similar-requests";

type SimilarRequestNoticePanelProps = {
  isJoining: boolean;
  isLoading: boolean;
  isQueryError: boolean;
  notice?: SimilarRequestNotice;
  onContinue: () => void;
  onJoin: (ticketId: string) => void;
  onRetry: () => void;
};

export function SimilarRequestNoticePanel({
  isJoining,
  isLoading,
  isQueryError,
  notice,
  onContinue,
  onJoin,
  onRetry,
}: SimilarRequestNoticePanelProps) {
  const matches = notice?.matches ?? [];

  if (isLoading) {
    return (
      <section className="surface similar-panel" aria-label="Similar request check">
        <p>Checking for similar open requests</p>
      </section>
    );
  }
  if (isQueryError) {
    return (
      <section className="surface similar-panel" aria-label="Similar request check">
        <div className="section-heading access-heading">
          <ShieldAlert aria-hidden="true" size={20} />
          <h2>Similar request check</h2>
        </div>
        <p className="auth-error" role="alert">
          In-progress requests could not be checked. Retry before deciding whether to create new
          work.
        </p>
        <div className="similar-panel__actions">
          <button onClick={onRetry} type="button">
            Retry check
          </button>
        </div>
      </section>
    );
  }
  if (matches.length === 0) {
    return null;
  }

  return (
    <section className="surface similar-panel" aria-label="Similar request check">
      <div className="section-heading access-heading">
        <GitMerge aria-hidden="true" size={20} />
        <h2>Similar request in progress</h2>
      </div>
      <p>A similar request appears to be in progress. You can join it or continue this one.</p>
      <div className="similar-panel__list">
        {matches.map((match) => (
          <article className="similar-match" key={match.ticketId}>
            <div>
              <strong>{match.reference}</strong>
              <span>{match.title}</span>
            </div>
            <Score value={match.score} />
            <div className="similar-match__reasons">
              {match.reasons.map((reason) => (
                <span key={reason}>{reason}</span>
              ))}
            </div>
            <button disabled={isJoining} onClick={() => onJoin(match.ticketId)} type="button">
              <Eye aria-hidden="true" size={16} />
              Join this work
            </button>
          </article>
        ))}
      </div>
      <div className="similar-panel__actions">
        <button className="store-action--secondary" onClick={onContinue} type="button">
          None answer my need
        </button>
      </div>
    </section>
  );
}

function Score({ value }: { value: number }) {
  return <span className="similar-score">{Math.round(value * 100)}%</span>;
}
