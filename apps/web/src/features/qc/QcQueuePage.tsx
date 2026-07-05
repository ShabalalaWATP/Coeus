import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

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
  const acgsQuery = useQuery({ queryKey: ["acgs"], queryFn: () => apiClient.listAcgs() });
  const detailQuery = useQuery({
    queryKey: ["qc-product", productId],
    queryFn: () => getQcProduct(productId ?? ""),
    enabled: productId !== undefined,
  });
  const products = queueQuery.data.products;
  const selectedProduct = useMemo(
    () =>
      actionResult ??
      detailQuery.data ??
      products.find((product) => product.ticketId === productId) ??
      products[0],
    [actionResult, detailQuery.data, productId, products],
  );
  const approveMutation = useMutation({
    mutationFn: () =>
      approveQcProduct(
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
      ),
    onSuccess: (product) => {
      setActionResult(product);
      updateQueue(queryClient, product);
    },
  });
  const rejectMutation = useMutation({
    mutationFn: () =>
      rejectQcProduct(selectedProduct.ticketId, releaseForm.rejectionReason, csrfToken),
    onSuccess: (product) => {
      setActionResult(product);
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
          {products.map((product) => (
            <Link
              className="request-row"
              key={product.ticketId}
              onClick={() => setActionResult(undefined)}
              to={`/qc/products/${product.ticketId}`}
            >
              <strong>{product.reference}</strong>
              <span>{product.title}</span>
              <small>{formatState(product.state)}</small>
            </Link>
          ))}
          {products.length === 0 ? <p>No products are awaiting QC.</p> : null}
        </aside>
        <QcProductDetail
          acgs={acgsQuery.data ?? []}
          checklist={checklist}
          onChecklistChange={setChecklist}
          onReleaseFormChange={setReleaseForm}
          onApprove={() => approveMutation.mutate()}
          onReject={() => rejectMutation.mutate()}
          product={selectedProduct}
          releaseForm={releaseForm}
        />
      </section>
    </div>
  );
}

function QcProductDetail({
  acgs,
  checklist,
  onApprove,
  onChecklistChange,
  onReject,
  onReleaseFormChange,
  product,
  releaseForm,
}: {
  acgs: AccessControlGroup[];
  checklist: Record<string, boolean>;
  onApprove: () => void;
  onChecklistChange: (checklist: Record<string, boolean>) => void;
  onReject: () => void;
  onReleaseFormChange: (form: QcReleaseFormState) => void;
  product: QcProduct | undefined;
  releaseForm: QcReleaseFormState;
}) {
  if (!product) {
    return (
      <section className="surface qc-detail" aria-label="QC product detail">
        <p>No QC product selected.</p>
      </section>
    );
  }
  const draft = product.latestDraft;
  const allChecklistComplete = product.checklistKeys.every((key) => checklist[key]);
  const canApprove = product.state === "QC_REVIEW" && allChecklistComplete;
  return (
    <section className="surface qc-detail" aria-label="QC product detail">
      <div className="section-heading">
        <h2>{product.reference}</h2>
        <p>{product.title}</p>
      </div>
      <ProductPreview product={product} />
      <MetadataChecks acgId={selectedAcgId(releaseForm, acgs)} product={product} />
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
      <ReleaseForm acgs={acgs} form={releaseForm} onChange={onReleaseFormChange} />
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
          <dd>{formatState(product.state)}</dd>
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

function formatState(state: string) {
  return state.replaceAll("_", " ");
}

function formatKey(key: string) {
  return key.replaceAll("_", " ");
}
