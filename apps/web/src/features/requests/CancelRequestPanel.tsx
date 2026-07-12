import { AlertTriangle } from "lucide-react";
import { useState } from "react";

type CancelRequestPanelProps = {
  isCancelling: boolean;
  onCancel: (reason: string, onSuccess?: () => void) => void;
};

export function CancelRequestPanel({ isCancelling, onCancel }: CancelRequestPanelProps) {
  const [reason, setReason] = useState("");
  const trimmedReason = reason.trim();

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (trimmedReason.length < 3) {
      return;
    }
    onCancel(trimmedReason, () => setReason(""));
  }

  return (
    <details className="workspace-details workspace-details--danger">
      <summary>
        <AlertTriangle aria-hidden="true" size={16} />
        Cancel request
      </summary>
      <form className="cancel-request-form" onSubmit={handleSubmit}>
        <p>Cancelling stops the request workflow and records the reason in the request history.</p>
        <label htmlFor="cancel-reason">Reason</label>
        <textarea
          id="cancel-reason"
          maxLength={300}
          onChange={(event) => setReason(event.target.value)}
          rows={3}
          value={reason}
        />
        <button disabled={isCancelling || trimmedReason.length < 3} type="submit">
          <AlertTriangle aria-hidden="true" size={16} />
          {isCancelling ? "Cancelling" : "Cancel request"}
        </button>
      </form>
    </details>
  );
}
