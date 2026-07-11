import { X } from "lucide-react";
import { useEffect, useRef } from "react";

import { JOURNEY_STAGES, stageIndexForState } from "./journey-stages";
import type { TicketState } from "../../lib/api-client/tickets";

type RequestJourneyProps = {
  onClose: () => void;
  state: TicketState;
};

export function RequestJourney({ onClose, state }: RequestJourneyProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const currentIndex = stageIndexForState(state);
  const reused = state === "CLOSED_EXISTING_PRODUCT_ACCEPTED";
  const cancelled = state === "CANCELLED";

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    dialog?.querySelector<HTMLElement>("button")?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
      if (event.key === "Tab" && dialog) {
        const focusable = [
          ...dialog.querySelectorAll<HTMLElement>(
            "button, [href], [tabindex]:not([tabindex='-1'])",
          ),
        ].filter((element) => !element.hasAttribute("disabled"));
        const first = focusable[0];
        const last = focusable.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      previousFocus?.focus();
    };
  }, [onClose]);

  return (
    <div className="journey-overlay" onClick={onClose} role="presentation">
      <section
        aria-label="Request journey"
        aria-modal="true"
        className="journey-dialog"
        onClick={(event) => event.stopPropagation()}
        ref={dialogRef}
        role="dialog"
      >
        <header className="journey-dialog__header">
          <div>
            <h2>Where your request goes</h2>
            <p>
              {cancelled
                ? "This request was cancelled, so it did not continue through the stages below."
                : reused
                  ? "An existing product satisfied this request, so it skipped straight to delivery."
                  : "Each stage is handled by a person supported by Istari agents."}
            </p>
          </div>
          <button aria-label="Close journey" onClick={onClose} type="button">
            <X aria-hidden="true" size={18} />
          </button>
        </header>
        <ol className="journey-steps">
          {JOURNEY_STAGES.map((stage, index) => {
            const Icon = stage.icon;
            const status = cancelled
              ? "next"
              : index < currentIndex
                ? "done"
                : index === currentIndex
                  ? "current"
                  : "next";
            return (
              <li className={`journey-step journey-step--${status}`} key={stage.label}>
                <span aria-hidden="true" className="journey-step__icon">
                  <Icon size={17} strokeWidth={1.9} />
                </span>
                <div>
                  <strong>{stage.label}</strong>
                  <span>{stage.detail}</span>
                </div>
                {status === "current" ? <em>You are here</em> : null}
              </li>
            );
          })}
        </ol>
      </section>
    </div>
  );
}
