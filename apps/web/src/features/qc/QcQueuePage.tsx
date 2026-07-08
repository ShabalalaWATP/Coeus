import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ErrorState } from "../../components/ui/PageState";
import { formatWorkflowState } from "../../lib/workflow/state-format";
import { apiClient, type AccessControlGroup } from "../../lib/api-client/client";
import {
  approveQcProduct,
  getQcProduct,
  listQcQueue,
  rejectQcProduct,
  type QcProduct,
  type QcQueue,
} from "../../lib/api-client/qc";
import { useAuth } from "../../lib/auth/auth-context";
import { useActionError } from "../../lib/mutations/action-error";
import {
  csvToValues,
  initialReleaseForm,
  selectedAcgId,
  type QcReleaseFormState,
} from "./qc-release-model";
import { MetadataChecks, PostReleaseStatus, ReleaseForm } from "./qc-release-sections";

const EMPTY_QUEUE: QcQueue = { products: [] };

export default function QcQueuePage() {
  const { productId } = useParams();
  const { session } = useAuth();
  const csrfToken = session?.csrfToken ?? "";
  const queryClient = useQueryClient();
  const [checklist, setChecklist] = useState<Record<string, boolean>>({});
  const [releaseForm, setReleaseForm] = useState(initialReleaseForm);
  const [actionResult, setActionResult] = useState<QcProduct>();
  const queueQuery = useQuery({
    queryKey: ["qc-queue"],
    queryFn: listQcQueue,
    initialData: EMPTY_QUEUE,
    initialDataUpdatedAt: 0,
  });
  const acgsQuery = useQuery({
    queryKey: ["acgs"],
    queryFn: () => apiClient.listAcgs(),
    retry: false,
  });
  const detailQuery = useQuery({
    queryKey: ["qc-product", productId],
    queryFn: () => getQcProduct(productId ?? ""),
    enabled: productId !== undefined,
  });
  const products = queueQuery.data.products;
  const routeProductMissingFromQueue =
    productId !== undefined && products.every((product) => product.ticketId !== productId);
  const requestedMissing =
    productId !== undefined && detailQuery.isError && routeProductMissingFromQueue;
  const requestedPending =
    productId !== undefined && detailQuery.isLoading && routeProductMissingFromQueue;
  const selectedProduct = useMemo(() => {
    if (requestedMissing || requestedPending) {
      return undefined;
    }
    return (
      actionResult ??
      detailQuery.data ??
      products.find((product) => product.ticketId === productId) ??
      products[0]
    );
  }, [actionResult, detailQuery.data, productId, products, requestedMissing, requestedPending]);
  const selectedProductId = selectedProduct?.ticketId;
  const { actionError, clearActionError, failActionWith } = useActionError();

  // Checklist ticks and release metadata belong to one product. Reset both
  // whenever the reviewer moves to a different product so state cannot leak.
  useEffect(() => {
    setChecklist({});
    setReleaseForm(initialReleaseForm);
  }, [selectedProductId]);

  const approveMutation = useMutation({
    mutationFn: () => {
      if (selectedProduct === undefined) {
        throw new Error("No QC product selected.");
      }
      return approveQcProduct(
        selectedProduct.ticketId,
        {
          checklist,
          classificationLevel: Number(releaseForm.classificationLevel),
          releasability: csvToValues(releaseForm.releasability),
          handlingCaveats: csvToValues(releaseForm.caveats),
          acgIds: [selectedAcgId(releaseForm, acgsQuery.data)],
          reason: releaseForm.reason,
        },
        csrfToken,
      );
    },
    onError: failActionWith("The product could not be approved. Try again."),
    onMutate: clearActionError,
    onSuccess: (product) => {
      setActionResult(product);
      updateQueue(queryClient, product);
    },
  });
  const rejectMutation = useMutation({
    mutationFn: () => {
      if (selectedProduct === undefined) {
        throw new Error("No QC product selected.");
      }
      return rejectQcProduct(selectedProduct.ticketId, releaseForm.rejectionReason, csrfToken);
    },
    onError: failActionWith("The product could not be returned to the analyst. Try again."),
    onMutate: clearActionError,
    onSuccess: (product) => {
      setActionResult(product);
      setReleaseForm((current) => ({ ...current, rejectionReason: "" }));
      updateQueue(queryClient, product);
    },
  });

  return (
    <div className="qc-page">
      <section className="overview-hero" aria-labelledby="qc-title">
        <div>
          <h1 id="qc-title">QC Queue</h1>
          <p>Review submitted products, release metadata and controlled dissemination.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>
      <section className="qc-grid">
        <aside className="surface qc-list" aria-label="QC products">
          <div className="section-heading">
            <h2>Submitted products</h2>
            <p>{products.length} products awaiting QC.</p>
          </div>
          {queueQuery.isError ? (
            <ErrorState onRetry={() => void queueQuery.refetch()} />
          ) : (
            <>
              {products.map((product) => (
                <Link
                  className="request-row"
                  key={product.ticketId}
                  onClick={() => setActionResult(undefined)}
                  to={`/qc/products/${encodeURIComponent(product.ticketId)}`}
                >
                  <strong>{product.reference}</strong>
                  <span>{product.title}</span>
                  <small>{formatWorkflowState(product.state)}</small>
                </Link>
              ))}
              {products.length === 0 ? <p>No products are awaiting QC.</p> : null}
            </>
          )}
        </aside>
        <QcProductDetail
          acgs={acgsQuery.data}
          acgsFailed={acgsQuery.isError}
          acgsLoading={acgsQuery.isLoading}
          actionError={actionError}
          checklist={checklist}
          onChecklistChange={setChecklist}
          onRetryAcgs={() => void acgsQuery.refetch()}
          onReleaseFormChange={setReleaseForm}
          onApprove={() => approveMutation.mutate()}
          onReject={() => rejectMutation.mutate()}
          product={selectedProduct}
          releaseForm={releaseForm}
          requestedMissing={requestedMissing}
        />
      </section>
    </div>
  );
}

function QcProductDetail({
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
  const releaseAcgId = selectedAcgId(releaseForm, acgs);
  const acgsUnavailable = acgsLoading || acgsFailed;
  const canApprove =
    product.state === "QC_REVIEW" &&
    allChecklistComplete &&
    releaseAcgId !== "" &&
    !acgsUnavailable;
  return (
    <section className="surface qc-detail" aria-label="QC product detail">
      {missingNotice}
      <div className="section-heading">
        <h2>{product.reference}</h2>
        <p>{product.title}</p>
      </div>
      <ProductPreview product={product} />
      <MetadataChecks acgId={releaseAcgId} product={product} />
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
        <button
          className="qc-secondary"
          onClick={() => onChecklistChange(keysToChecklist(product.checklistKeys))}
          type="button"
        >
          <CheckCircle2 aria-hidden="true" size={18} /> Mark all complete
        </button>
        {product.checklistKeys.map((key) => (
          <label className="qc-check" key={key}>
            <input
              checked={Boolean(checklist[key])}
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
        form={releaseForm}
        onChange={onReleaseFormChange}
      />
      <div className="qc-actions">
        <button disabled={!canApprove} onClick={onApprove} type="button">
          <CheckCircle2 aria-hidden="true" size={18} /> Approve and disseminate
        </button>
        <button
          disabled={product.state !== "QC_REVIEW" || releaseForm.rejectionReason.trim().length < 3}
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
      {draft === null ? null : (
        <p className="qc-footnote">
          Latest draft v{draft.versionNumber} by {draft.createdByUserId}
        </p>
      )}
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

function updateQueue(queryClient: ReturnType<typeof useQueryClient>, product: QcProduct) {
  queryClient.setQueryData<QcQueue>(["qc-queue"], (current) => ({
    products: (current?.products ?? []).filter((item) => item.ticketId !== product.ticketId),
  }));
}

function keysToChecklist(keys: string[]) {
  return Object.fromEntries(keys.map((key) => [key, true]));
}

function formatKey(key: string) {
  return key.replaceAll("_", " ");
}
