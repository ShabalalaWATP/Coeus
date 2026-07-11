import { ShieldAlert } from "lucide-react";

type AiProviderActivationWarningProps = {
  onCancel: () => void;
  onConfirm: () => void;
  pending: boolean;
  providerLabel: string;
};

export function AiProviderActivationWarning({
  onCancel,
  onConfirm,
  pending,
  providerLabel,
}: AiProviderActivationWarningProps) {
  return (
    <div aria-label="Confirm provider change" className="ai-activate-warning" role="alertdialog">
      <ShieldAlert aria-hidden="true" size={18} />
      <div>
        <strong>This changes the AI provider for every user immediately.</strong>
        <p>
          All intake assistant replies will be produced by {providerLabel} and all administrators
          will be notified of this change. Test the connection first.
        </p>
        <div className="ai-actions">
          <button className="ai-btn-primary" disabled={pending} onClick={onConfirm} type="button">
            Confirm and activate
          </button>
          <button className="ai-btn-secondary" onClick={onCancel} type="button">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
