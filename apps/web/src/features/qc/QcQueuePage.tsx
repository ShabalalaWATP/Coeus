import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ErrorState, LoadingState } from "../../components/ui/PageState";
import { formatWorkflowState } from "../../lib/workflow/state-format";
import { listAcgs } from "../../lib/api-client/access";
import {
  approveQcProduct,
  claimQcProduct,
  getQcProduct,
  listQcQueue,
  releaseQcClaim,
  rejectQcProduct,
  type QcProduct,
  type QcQueue,
  type QcQueueItem,
} from "../../lib/api-client/qc";
import { useAuth } from "../../lib/auth/auth-context";
import { useActionError } from "../../lib/mutations/action-error";
import { csvToValues, initialReleaseForm, selectedAcgId } from "./qc-release-model";
import { QcProductDetail } from "./qc-product-detail";

const EMPTY_QUEUE: QcQueue = { items: [], products: [] };

export default function QcQueuePage() {
  const { productId } = useParams();
  const { session } = useAuth();
  const csrfToken = session?.csrfToken ?? "";
  const queryClient = useQueryClient();
  const navigate = useNavigate();
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
  const items = queueQuery.data.items;
  const routeProductMissingFromQueue =
    productId !== undefined &&
    products.every((product) => product.ticketId !== productId) &&
    items.every((item) => item.ticketId !== productId);
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

  const claimMutation = useMutation({
    mutationFn: (item: QcQueueItem) => claimQcProduct(item.ticketId, csrfToken),
    onError: failActionWith("The product could not be claimed. Refresh and try again."),
    onMutate: clearActionError,
    onSuccess: (product) => {
      setActionResult(product);
      updateQueueAfterClaim(queryClient, product);
      void navigate(`/qc/products/${encodeURIComponent(product.ticketId)}`);
    },
  });
  const releaseMutation = useMutation({
    mutationFn: async () => {
      if (selectedProduct === undefined) {
        throw new Error("No QC product selected.");
      }
      await releaseQcClaim(selectedProduct.ticketId, csrfToken);
      return selectedProduct.ticketId;
    },
    onError: failActionWith("The claim could not be released. Refresh and try again."),
    onMutate: clearActionError,
    onSuccess: (ticketId) => {
      setActionResult(undefined);
      updateQueueAfterRelease(queryClient, ticketId);
      void navigate("/qc/queue");
    },
  });

  // Checklist ticks and release metadata belong to one product. Reset both
  // whenever the reviewer moves to a different product so state cannot leak.
  useLayoutEffect(() => {
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
  const actionPending =
    approveMutation.isPending ||
    claimMutation.isPending ||
    rejectMutation.isPending ||
    releaseMutation.isPending;

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
              {items.length} {items.length === 1 ? "product" : "products"} awaiting QC.
            </p>
          </div>
          {queueQuery.isError ? (
            <ErrorState onRetry={() => void queueQuery.refetch()} />
          ) : queueQuery.isFetching && queueQuery.dataUpdatedAt === 0 ? (
            <LoadingState label="Loading QC products" />
          ) : (
            <>
              {items.map((item) =>
                item.claimStatus === "claimed_by_you" ? (
                  <Link
                    aria-current={item.ticketId === selectedProductId ? "page" : undefined}
                    aria-disabled={actionPending || undefined}
                    className="request-row"
                    key={item.ticketId}
                    onClick={(event) => {
                      if (actionPending) {
                        event.preventDefault();
                        return;
                      }
                      setActionResult(undefined);
                    }}
                    to={`/qc/products/${encodeURIComponent(item.ticketId)}`}
                  >
                    <strong>{item.reference}</strong>
                    <span>Assigned to you</span>
                    <small>{formatWorkflowState(item.state)}</small>
                  </Link>
                ) : item.claimStatus === "available" ? (
                  <button
                    className="request-row"
                    disabled={actionPending}
                    key={item.ticketId}
                    onClick={() => claimMutation.mutate(item)}
                    type="button"
                  >
                    <strong>{item.reference}</strong>
                    <span>Available for review</span>
                    <small>Claim product</small>
                  </button>
                ) : (
                  <div aria-disabled="true" className="request-row" key={item.ticketId}>
                    <strong>{item.reference}</strong>
                    <span>Claimed by another reviewer</span>
                    <small>{formatWorkflowState(item.state)}</small>
                  </div>
                ),
              )}
              {items.length === 0 ? <p>No products are awaiting QC.</p> : null}
              {selectedProduct === undefined && actionError ? (
                <p className="error-text" role="alert">
                  {actionError}
                </p>
              ) : null}
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
          onReleaseClaim={() => releaseMutation.mutate()}
          product={selectedProduct}
          releaseForm={releaseForm}
          requestedMissing={requestedMissing}
          requestedPending={requestedPending}
        />
      </section>
    </div>
  );
}

function updateQueue(queryClient: ReturnType<typeof useQueryClient>, product: QcProduct) {
  queryClient.setQueryData<QcQueue>(["qc-queue"], (current) => ({
    items: (current?.items ?? []).filter((item) => item.ticketId !== product.ticketId),
    products: (current?.products ?? []).filter((item) => item.ticketId !== product.ticketId),
  }));
}

function updateQueueAfterClaim(queryClient: ReturnType<typeof useQueryClient>, product: QcProduct) {
  queryClient.setQueryData<QcQueue>(["qc-queue"], (current) => ({
    items: (current?.items ?? []).map((item) =>
      item.ticketId === product.ticketId ? { ...item, claimStatus: "claimed_by_you" } : item,
    ),
    products: [
      ...(current?.products ?? []).filter((item) => item.ticketId !== product.ticketId),
      product,
    ],
  }));
}

function updateQueueAfterRelease(queryClient: ReturnType<typeof useQueryClient>, ticketId: string) {
  queryClient.setQueryData<QcQueue>(["qc-queue"], (current) => ({
    items: (current?.items ?? []).map((item) =>
      item.ticketId === ticketId ? { ...item, claimStatus: "available" } : item,
    ),
    products: (current?.products ?? []).filter((item) => item.ticketId !== ticketId),
  }));
}
