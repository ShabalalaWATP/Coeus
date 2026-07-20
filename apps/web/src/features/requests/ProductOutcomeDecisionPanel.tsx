import { CheckCircle2, RotateCcw } from "lucide-react";
import { useState } from "react";

type ProductOutcomeDecisionPanelProps = {
  disabled: boolean;
  onDecide: (meetsRequirement: boolean, reason: string, unmetCriteria: string[]) => void;
};

export function ProductOutcomeDecisionPanel({
  disabled,
  onDecide,
}: ProductOutcomeDecisionPanelProps) {
  const [showRejection, setShowRejection] = useState(false);
  const [reason, setReason] = useState("");
  const [criteria, setCriteria] = useState("");
  const cleanedReason = reason.trim();
  return (
    <section className="product-outcome-decision" aria-label="Released product decision">
      <strong>Does the released product meet your requirement?</strong>
      <p>
        Review the product before deciding. A rejection is returned to the responsible manager with
        your explanation.
      </p>
      <div className="request-register-row__decision-actions">
        <button
          className="request-register-row__action"
          disabled={disabled}
          onClick={() => onDecide(true, "The released product meets the requirement.", [])}
          type="button"
        >
          <CheckCircle2 aria-hidden="true" size={15} />
          Yes, close request
        </button>
        <button
          className="request-register-row__action"
          disabled={disabled}
          onClick={() => setShowRejection((current) => !current)}
          type="button"
        >
          <RotateCcw aria-hidden="true" size={15} />
          No, request re-analysis
        </button>
      </div>
      {showRejection ? (
        <div className="product-outcome-decision__reason">
          <label>
            Why does it not meet the requirement?
            <textarea
              disabled={disabled}
              onChange={(event) => setReason(event.target.value)}
              value={reason}
            />
          </label>
          <label>
            Unmet criteria (optional, comma separated)
            <input
              disabled={disabled}
              onChange={(event) => setCriteria(event.target.value)}
              value={criteria}
            />
          </label>
          <button
            disabled={disabled || cleanedReason.length < 3}
            onClick={() =>
              onDecide(
                false,
                cleanedReason,
                criteria
                  .split(",")
                  .map((item) => item.trim())
                  .filter(Boolean),
              )
            }
            type="button"
          >
            Send to manager for review
          </button>
        </div>
      ) : null}
    </section>
  );
}
