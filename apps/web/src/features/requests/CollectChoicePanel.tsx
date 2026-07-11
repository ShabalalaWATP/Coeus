import { Microscope, PackageSearch, Route } from "lucide-react";

type CollectChoicePanelProps = {
  isPending: boolean;
  onChoose: (analysed: boolean) => void;
};

export function CollectChoicePanel({ isPending, onChoose }: CollectChoicePanelProps) {
  return (
    <section className="surface no-match-panel" aria-labelledby="collect-choice-title">
      <div className="section-heading access-heading">
        <Route aria-hidden="true" size={20} />
        <h2 id="collect-choice-title">Collection has been approved</h2>
      </div>
      <p>
        JIOC has routed this request to the collection team. Choose how you would like the collected
        material delivered.
      </p>
      <div className="no-match-panel__actions">
        <button disabled={isPending} onClick={() => onChoose(false)} type="button">
          <PackageSearch aria-hidden="true" size={18} />
          Raw collect only
        </button>
        <button disabled={isPending} onClick={() => onChoose(true)} type="button">
          <Microscope aria-hidden="true" size={18} />
          Collect plus RFA analysis
        </button>
      </div>
    </section>
  );
}
