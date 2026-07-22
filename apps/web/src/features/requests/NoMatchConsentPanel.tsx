import { CheckCircle2, HelpCircle, XCircle } from "lucide-react";

type NoMatchConsentPanelProps = {
  isPending: boolean;
  onConsent: (taskAsNewRequest: boolean) => void;
};

export function NoMatchConsentPanel({ isPending, onConsent }: NoMatchConsentPanelProps) {
  return (
    <section className="surface no-match-panel" aria-labelledby="no-match-title">
      <div className="section-heading access-heading">
        <HelpCircle aria-hidden="true" size={20} />
        <h2 id="no-match-title">No accepted existing answer</h2>
      </div>
      <p>
        The Intelligence Store search did not answer your question. Do you want Istari to create new
        tasking?
      </p>
      <div className="no-match-panel__actions">
        <button disabled={isPending} onClick={() => onConsent(true)} type="button">
          <CheckCircle2 aria-hidden="true" size={18} />
          Yes, task as new request
        </button>
        <button
          className="store-action--secondary"
          disabled={isPending}
          onClick={() => onConsent(false)}
          type="button"
        >
          <XCircle aria-hidden="true" size={18} />
          No, close unanswered
        </button>
      </div>
    </section>
  );
}
