import { AnalystDraftForm } from "./AnalystDraftForm";
import { AnalystConversation } from "./AnalystConversation";
import { AnalystTaskContext } from "./AnalystTaskContext";
import { LinkedProductsPanel, NotesPanel, WorkPackagesPanel } from "./AnalystTaskPanels";
import { canSubmitTask, submissionBlockers } from "./analyst-task-policy";
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
  const blockers = submissionBlockers(task);

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
      <AnalystConversation ticketId={task.ticketId} />
      <WorkPackagesPanel
        disabled={actions.actionPending}
        onComplete={actions.completePackage}
        task={task}
      />
      <NotesPanel
        disabled={actions.actionPending}
        noteBody={actions.noteBody}
        onNoteChange={actions.setNoteBody}
        onSubmit={actions.submitNote}
        task={task}
      />
      <LinkedProductsPanel
        disabled={actions.actionPending}
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
          disabled={actions.actionPending}
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
      {blockers.length ? (
        <div className="analyst-submit-guidance" role="status">
          <strong>Before submission</strong>
          <ul>
            {blockers.map((blocker) => (
              <li key={blocker}>{blocker}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <button
        className="analyst-submit"
        disabled={!canSubmitTask(task) || actions.actionPending}
        onClick={actions.submit}
        type="button"
      >
        {task.state === "REWORK_REQUIRED" ? "Resubmit to QC" : "Submit for manager approval"}
      </button>
    </section>
  );
}
