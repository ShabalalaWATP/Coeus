import type { AnalystTask } from "../../lib/api-client/analyst";
import { workflowProductPreviewUrl } from "../../lib/api-client/analyst";
import { ControlledDocumentViewer } from "../../components/product/ControlledDocumentViewer";
import { productTypeLabel } from "../store/store-options";

type ManagerWorkReviewProps = {
  task: AnalystTask;
};

export function ManagerWorkReview({ task }: ManagerWorkReviewProps) {
  const latestDraft = task.drafts.at(-1);
  const primaryAsset = latestDraft?.assets[0];

  return (
    <section className="manager-work-review" aria-label="Submitted analyst work">
      <div className="manager-work-review__heading">
        <div>
          <p className="eyebrow">Submitted analyst work</p>
          <h4>{latestDraft?.title ?? "No draft submitted"}</h4>
        </div>
        {latestDraft ? <span>Version {latestDraft.versionNumber}</span> : null}
      </div>
      {latestDraft ? (
        <>
          <p>{latestDraft.summary}</p>
          {primaryAsset?.previewAvailable ? (
            <ControlledDocumentViewer
              kind={primaryAsset.previewKind}
              title={`${latestDraft.title} manager preview`}
              url={workflowProductPreviewUrl(task.ticketId, latestDraft.id, primaryAsset.id)}
            />
          ) : (
            <div className="manager-work-review__content">{latestDraft.content}</div>
          )}
          <dl className="manager-work-review__facts">
            <div>
              <dt>Product type</dt>
              <dd>{productTypeLabel(latestDraft.productType)}</dd>
            </div>
            <div>
              <dt>Assigned analysts</dt>
              <dd>{task.assignments.length}</dd>
            </div>
            <div>
              <dt>Supporting products</dt>
              <dd>{task.linkedProducts.length}</dd>
            </div>
            <div>
              <dt>Draft assets</dt>
              <dd>{latestDraft.assets.length}</dd>
            </div>
          </dl>
        </>
      ) : (
        <p role="alert">Approval is unavailable until a submitted draft can be reviewed.</p>
      )}
      <div className="manager-work-review__packages">
        <h4>Work packages</h4>
        <ul>
          {task.workPackages.map((workPackage) => (
            <li key={workPackage.id}>
              <span>{workPackage.title}</span>
              <strong>{workPackage.status === "complete" ? "Complete" : "Pending"}</strong>
            </li>
          ))}
        </ul>
      </div>
      {task.notes.length > 0 ? (
        <details>
          <summary>Working notes ({task.notes.length})</summary>
          <ul>
            {task.notes.map((note) => (
              <li key={note.id}>{note.body}</li>
            ))}
          </ul>
        </details>
      ) : null}
      {task.linkedProducts.length > 0 ? (
        <details>
          <summary>Supporting products ({task.linkedProducts.length})</summary>
          <ul>
            {task.linkedProducts.map((product) => (
              <li key={product.id}>
                <strong>{product.reference}</strong> {product.title}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
