import { CheckCircle2, HelpCircle, Search, XCircle } from "lucide-react";

type NoMatchConsentPanelProps = {
  canDecide?: boolean;
  canRefine?: boolean;
  isPending: boolean;
  isRefining?: boolean;
  onConsent: (taskAsNewRequest: boolean) => void;
  onRefine?: () => void;
};

export function NoMatchConsentPanel({
  canDecide = true,
  canRefine = false,
  isPending,
  isRefining = false,
  onConsent,
  onRefine,
}: NoMatchConsentPanelProps) {
  return (
    <section className="surface no-match-panel" aria-labelledby="no-match-title">
      <div className="section-heading access-heading">
        <HelpCircle aria-hidden="true" size={20} />
        <h2 id="no-match-title">No accepted existing answer</h2>
      </div>
      <p>
        {canRefine && canDecide
          ? "Use your feedback to search again, or continue if new work is needed."
          : canRefine
            ? "Use your feedback to retry the search before deciding whether new work is needed."
            : "The Intelligence Store search did not answer your question. Do you want new work to be tasked?"}
      </p>
      {canDecide ? (
        <p className="field-hint">
          If you continue, the JIOC Agent will decide whether RFA, collection, clarification or
          human review is appropriate.
        </p>
      ) : null}
      <div className="no-match-panel__actions">
        {canRefine && onRefine ? (
          <button disabled={isPending || isRefining} onClick={onRefine} type="button">
            <Search aria-hidden="true" size={18} />
            {isRefining ? "Searching…" : "Refine and search again"}
          </button>
        ) : null}
        {canDecide ? (
          <>
            <button
              disabled={isPending || isRefining}
              onClick={() => onConsent(true)}
              type="button"
            >
              <CheckCircle2 aria-hidden="true" size={18} />
              Continue to the JIOC Agent
            </button>
            <button
              className="store-action--secondary"
              disabled={isPending || isRefining}
              onClick={() => onConsent(false)}
              type="button"
            >
              <XCircle aria-hidden="true" size={18} />
              Close as unfulfilled
            </button>
          </>
        ) : null}
      </div>
    </section>
  );
}
