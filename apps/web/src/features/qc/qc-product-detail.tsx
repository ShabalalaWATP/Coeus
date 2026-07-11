import { CheckCircle2, RotateCcw } from "lucide-react";
import { Link } from "react-router-dom";

import { formatWorkflowState } from "../../lib/workflow/state-format";
import type { AccessControlGroup } from "../../lib/api-client/access";
import type { QcProduct } from "../../lib/api-client/qc";
import { selectedAcgId, type QcReleaseFormState } from "./qc-release-model";
import { MetadataChecks, PostReleaseStatus, ReleaseForm } from "./qc-release-sections";

export function QcProductDetail({
  actionPending,
  acgs,
  acgsFailed,
  acgsLoading,
  actionError,
  checklist,
  onApprove,
  onChecklistChange,
  onReject,
  onRetryAcgs,
  onReleaseFormChange,
  product,
  releaseForm,
  requestedMissing,
}: {
  actionPending: boolean;
  acgs: AccessControlGroup[] | undefined;
  acgsFailed: boolean;
  acgsLoading: boolean;
  actionError: string | null;
  checklist: Record<string, boolean>;
  onApprove: () => void;
  onChecklistChange: (checklist: Record<string, boolean>) => void;
  onReject: () => void;
  onRetryAcgs: () => void;
  onReleaseFormChange: (form: QcReleaseFormState) => void;
  product: QcProduct | undefined;
  releaseForm: QcReleaseFormState;
  requestedMissing: boolean;
}) {
  const missingNotice = requestedMissing ? (
    <p className="workspace-alert" role="alert">
      The requested product was not found or is no longer in the QC queue.{" "}
      <Link to="/qc/queue">Back to the QC queue</Link>
    </p>
  ) : null;
  if (!product) {
    return (
      <section className="surface qc-detail" aria-label="QC product detail">
        {missingNotice}
        <p>No QC product selected.</p>
      </section>
    );
  }
  const draft = product.latestDraft;
  const allChecklistComplete = product.checklistKeys.every((key) => checklist[key]);
  const releaseAcgId = selectedAcgId(releaseForm);
  const acgsUnavailable = acgsLoading || acgsFailed;
  const classificationLevel = Number(releaseForm.classificationLevel);
  const canApprove =
    product.state === "QC_REVIEW" &&
    Boolean(draft?.content) &&
    Boolean(draft?.assets.length) &&
    allChecklistComplete &&
    releaseAcgId !== "" &&
    releaseForm.releasability.trim().length > 0 &&
    releaseForm.reason.trim().length >= 3 &&
    Number.isInteger(classificationLevel) &&
    classificationLevel >= 0 &&
    classificationLevel <= 5 &&
    !acgsUnavailable &&
    !actionPending;
  return (
    <section className="surface qc-detail" aria-label="QC product detail">
      {missingNotice}
      <div className="section-heading">
        <h2>{product.reference}</h2>
        <p>{product.title}</p>
      </div>
      <ProductPreview product={product} />
      <MetadataChecks acgId={releaseAcgId} form={releaseForm} product={product} />
      {acgsFailed ? (
        <div className="workspace-alert" role="alert">
          <span>Access groups could not be loaded. Refresh and try again.</span>
          <button onClick={onRetryAcgs} type="button">
            Retry access groups
          </button>
        </div>
      ) : null}
      <section className="qc-panel">
        <h3>QC checklist</h3>
        <p>Review and confirm every control individually before approving the product.</p>
        {product.checklistKeys.map((key) => (
          <label className="qc-check" key={key}>
            <input
              checked={Boolean(checklist[key])}
              disabled={actionPending}
              onChange={(event) => onChecklistChange({ ...checklist, [key]: event.target.checked })}
              type="checkbox"
            />
            <span>{formatKey(key)}</span>
          </label>
        ))}
      </section>
      <ReleaseForm
        acgSelectDisabled={acgsUnavailable}
        acgs={acgs ?? []}
        disabled={actionPending}
        form={releaseForm}
        onChange={onReleaseFormChange}
      />
      <div className="qc-actions">
        <button disabled={!canApprove} onClick={onApprove} type="button">
          <CheckCircle2 aria-hidden="true" size={18} /> Approve and disseminate
        </button>
        <button
          disabled={
            actionPending ||
            product.state !== "QC_REVIEW" ||
            releaseForm.rejectionReason.trim().length < 3
          }
          onClick={onReject}
          type="button"
        >
          <RotateCcw aria-hidden="true" size={18} /> Return to analyst
        </button>
      </div>
      {actionError ? (
        <p className="auth-error" role="alert">
          {actionError}
        </p>
      ) : null}
      <PostReleaseStatus product={product} />
      {draft === null ? null : <p className="qc-footnote">Latest draft v{draft.versionNumber}</p>}
    </section>
  );
}

function ProductPreview({ product }: { product: QcProduct }) {
  const draft = product.latestDraft;
  return (
    <section className="qc-panel">
      <h3>Product preview</h3>
      <dl className="qc-metadata">
        <div>
          <dt>State</dt>
          <dd>{formatWorkflowState(product.state)}</dd>
        </div>
        <div>
          <dt>Region</dt>
          <dd>{product.areaOrRegion ?? "Not set"}</dd>
        </div>
        <div>
          <dt>Output</dt>
          <dd>{product.requiredOutputFormat ?? "Not set"}</dd>
        </div>
      </dl>
      <p>{product.operationalQuestion}</p>
      {draft === null ? <p>No draft product is attached.</p> : <p>{draft.summary}</p>}
      {draft === null ? null : <pre className="qc-preview">{draft.content}</pre>}
    </section>
  );
}

function formatKey(key: string) {
  return key.replaceAll("_", " ");
}
