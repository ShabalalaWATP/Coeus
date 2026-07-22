import { ShieldAlert } from "lucide-react";
import { useEffect, useRef } from "react";

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
  const cancelRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  useEffect(() => cancelRef.current?.focus(), []);
  return (
    <div
      aria-label="Confirm provider change"
      aria-modal="true"
      className="ai-activate-warning"
      onKeyDown={(event) => {
        if (event.key === "Escape" && !pending) onCancel();
        if (event.key === "Tab") {
          const buttons = Array.from(
            dialogRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [],
          );
          const first = buttons[0];
          const last = buttons.at(-1);
          if (!first || !last) return;
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }
      }}
      ref={dialogRef}
      role="alertdialog"
    >
      <ShieldAlert aria-hidden="true" size={18} />
      <div>
        <strong>This changes the AI provider for every user immediately.</strong>
        <p>
          {providerLabel} becomes the remote text and advisory provider where egress is approved.
          Deterministic fallback remains available, and all administrators will be notified. Test
          the connection first.
        </p>
        <div className="ai-actions">
          <button className="ai-btn-primary" disabled={pending} onClick={onConfirm} type="button">
            Confirm and activate
          </button>
          <button
            className="ai-btn-secondary"
            disabled={pending}
            onClick={onCancel}
            ref={cancelRef}
            type="button"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
