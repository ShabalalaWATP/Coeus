import { Inbox, RefreshCw, ShieldAlert } from "lucide-react";

type LoadingStateProps = {
  label?: string;
};

export function LoadingState({ label = "Loading" }: LoadingStateProps) {
  return (
    <div className="surface--loading" role="status">
      <span className="loading-pulse" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

type ErrorStateProps = {
  message?: string;
  onRetry?: () => void;
};

export function ErrorState({
  message = "This view could not be loaded. Try again or contact an administrator.",
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="page-state page-state--error" role="alert">
      <ShieldAlert aria-hidden="true" size={22} />
      <h2>Unable to load data</h2>
      <p>{message}</p>
      {onRetry === undefined ? null : (
        <button onClick={onRetry} type="button">
          <RefreshCw aria-hidden="true" size={16} />
          Retry
        </button>
      )}
    </div>
  );
}

type EmptyStateProps = {
  title: string;
  hint?: string;
};

export function EmptyState({ hint, title }: EmptyStateProps) {
  return (
    <div className="page-state">
      <Inbox aria-hidden="true" size={22} />
      <h2>{title}</h2>
      {hint === undefined ? null : <p>{hint}</p>}
    </div>
  );
}
