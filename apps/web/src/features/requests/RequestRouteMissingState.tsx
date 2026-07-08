import { EmptyState } from "../../components/ui/PageState";

type RequestRouteMissingStateProps = {
  onBack: () => void;
};

export function RequestRouteMissingState({ onBack }: RequestRouteMissingStateProps) {
  return (
    <section className="surface">
      <EmptyState
        hint="This request is not visible to your account or no longer exists."
        title="Request not found"
      />
      <button className="store-action store-action--secondary" onClick={onBack} type="button">
        Back to my requests
      </button>
    </section>
  );
}
