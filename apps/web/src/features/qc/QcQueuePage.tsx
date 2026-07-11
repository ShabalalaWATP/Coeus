import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ErrorState } from "../../components/ui/PageState";
import { formatWorkflowState } from "../../lib/workflow/state-format";
import { listAcgs } from "../../lib/api-client/access";
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
import { csvToValues, initialReleaseForm, selectedAcgId } from "./qc-release-model";
import { QcProductDetail } from "./qc-product-detail";

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
    queryFn: listAcgs,
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
    productId !== undefined &&
    detailQuery.isError &&
    routeProductMissingFromQueue &&
    !queueQuery.isError;
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
          acgIds: [selectedAcgId(releaseForm)],
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
  const actionPending = approveMutation.isPending || rejectMutation.isPending;

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
            <p>
              {products.length} {products.length === 1 ? "product" : "products"} awaiting QC.
            </p>
          </div>
          {queueQuery.isError ? (
            <ErrorState onRetry={() => void queueQuery.refetch()} />
          ) : (
            <>
              {products.map((product) => (
                <Link
                  aria-current={product.ticketId === selectedProductId ? "page" : undefined}
                  aria-disabled={actionPending || undefined}
                  className="request-row"
                  key={product.ticketId}
                  onClick={(event) => {
                    if (actionPending) {
                      event.preventDefault();
                      return;
                    }
                    setActionResult(undefined);
                  }}
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
          actionPending={actionPending}
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

function updateQueue(queryClient: ReturnType<typeof useQueryClient>, product: QcProduct) {
  queryClient.setQueryData<QcQueue>(["qc-queue"], (current) => ({
    products: (current?.products ?? []).filter((item) => item.ticketId !== product.ticketId),
  }));
}
