import { useState } from "react";

import type { CalendarCommitment } from "../../lib/api-client/workforce-calendar";

type Props = {
  commitment: CalendarCommitment;
  disabled: boolean;
  onRespond: (
    commitment: CalendarCommitment,
    state: "acknowledged" | "disputed",
    reason?: string,
  ) => void;
};

export function CalendarCommitmentActions({ commitment, disabled, onRespond }: Props) {
  const [disputing, setDisputing] = useState(false);
  const [reason, setReason] = useState("");
  return (
    <div className="calendar-commitment" aria-label="Manager commitment response">
      <span className={`calendar-commitment__state is-${commitment.responseState}`}>
        {commitment.responseState === "pending"
          ? "Response needed"
          : commitment.responseState === "acknowledged"
            ? "Acknowledged"
            : "Disputed"}
      </span>
      {commitment.responseState === "pending" && !disputing ? (
        <span className="calendar-commitment__buttons">
          <button
            disabled={disabled}
            onClick={() => onRespond(commitment, "acknowledged")}
            type="button"
          >
            Acknowledge
          </button>
          <button disabled={disabled} onClick={() => setDisputing(true)} type="button">
            Dispute
          </button>
        </span>
      ) : null}
      {disputing ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onRespond(commitment, "disputed", reason.trim());
          }}
        >
          <label>
            Why does this commitment need changing?
            <textarea
              maxLength={500}
              onChange={(event) => setReason(event.target.value)}
              required
              value={reason}
            />
          </label>
          <span className="calendar-commitment__buttons">
            <button disabled={disabled || !reason.trim()} type="submit">
              Send dispute
            </button>
            <button onClick={() => setDisputing(false)} type="button">
              Keep commitment
            </button>
          </span>
        </form>
      ) : null}
    </div>
  );
}
