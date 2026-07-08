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
  const hiddenOnly = matches.length === 0 && notice?.hiddenMatchesPresent === true;

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
          Similar requests could not be checked. Try again or continue this request.
        </p>
        <div className="similar-panel__actions">
          <button onClick={onRetry} type="button">
            Retry check
          </button>
          <button className="store-action--secondary" onClick={onContinue} type="button">
            Continue request
          </button>
        </div>
      </section>
    );
  }
  if (matches.length === 0 && !hiddenOnly) {
    return null;
  }

  return (
    <section className="surface similar-panel" aria-label="Similar request check">
      <div className="section-heading access-heading">
        <GitMerge aria-hidden="true" size={20} />
        <h2>Similar request in progress</h2>
      </div>
      {hiddenOnly ? (
        <p>
          The assessing team will check for overlapping work before tasking continues. No ticket
          details are shown unless you already have access.
        </p>
      ) : (
        <>
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
                  Join as viewer
                </button>
              </article>
            ))}
          </div>
        </>
      )}
      <div className="similar-panel__actions">
        <button className="store-action--secondary" onClick={onContinue} type="button">
          Continue request
        </button>
      </div>
    </section>
  );
}

function Score({ value }: { value: number }) {
  return <span className="similar-score">{Math.round(value * 100)}%</span>;
}
