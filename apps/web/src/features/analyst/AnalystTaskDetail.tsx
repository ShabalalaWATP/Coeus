import { AnalystDraftForm } from "./AnalystDraftForm";
import { AnalystTaskContext } from "./AnalystTaskContext";
import { LinkedProductsPanel, NotesPanel, WorkPackagesPanel } from "./AnalystTaskPanels";
import { canSubmitTask } from "./analyst-task-policy";
import { useAnalystTaskActions } from "./useAnalystTaskActions";
import type { AnalystTask } from "../../lib/api-client/analyst";

type AnalystTaskDetailProps = {
  task: AnalystTask | undefined;
  onTaskChange: (task: AnalystTask) => void;
};

export default function AnalystTaskDetail({ onTaskChange, task }: AnalystTaskDetailProps) {
  const actions = useAnalystTaskActions(task, onTaskChange);

  if (!task) {
    return (
      <section className="surface analyst-detail" aria-label="Analyst task detail">
        <p>No assigned task selected.</p>
      </section>
    );
  }

  return (
    <section className="surface analyst-detail" aria-label="Analyst task detail">
      <div className="section-heading">
        <h2>{task.reference}</h2>
        <p>{task.title}</p>
      </div>
      {actions.actionError ? (
        <p className="auth-error" role="alert">
          {actions.actionError}
        </p>
      ) : null}
      <AnalystTaskContext task={task} />
      <WorkPackagesPanel onComplete={actions.completePackage} task={task} />
      <NotesPanel
        noteBody={actions.noteBody}
        onNoteChange={actions.setNoteBody}
        onSubmit={actions.submitNote}
        task={task}
      />
      <LinkedProductsPanel
        isError={actions.productsQuery.isError}
        onLink={actions.linkProduct}
        onQueryChange={actions.setProductQuery}
        onRetry={actions.retryProductSearch}
        onSearch={actions.searchProducts}
        products={actions.productsQuery.data?.products ?? []}
        productQuery={actions.productQuery}
        task={task}
      />
      <section className="analyst-panel">
        <h3>Draft product</h3>
        <AnalystDraftForm
          draft={actions.draft}
          onChange={actions.setDraft}
          onSubmit={actions.saveDraft}
        />
        <ol className="analyst-list-items">
          {task.drafts.map((item) => (
            <li key={item.id}>
              v{item.versionNumber}: {item.title}
            </li>
          ))}
        </ol>
      </section>
      <button
        className="analyst-submit"
        disabled={!canSubmitTask(task) || actions.submitPending}
        onClick={actions.submit}
        type="button"
      >
        {task.state === "REWORK_REQUIRED" ? "Resubmit to QC" : "Submit for manager approval"}
      </button>
    </section>
  );
}
