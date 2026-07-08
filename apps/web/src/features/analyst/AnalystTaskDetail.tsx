import { useMutation, useQuery } from "@tanstack/react-query";
import { Link2, StickyNote } from "lucide-react";
import { useState } from "react";

import { AnalystDraftForm } from "./AnalystDraftForm";
import { AnalystTaskContext } from "./AnalystTaskContext";
import {
  addAnalystNote,
  linkAnalystProduct,
  saveDraftProduct,
  submitTaskToQc,
  updateWorkPackage,
  type AnalystTask,
} from "../../lib/api-client/analyst";
import { searchStoreProducts, type StoreSearchResponse } from "../../lib/api-client/store";
import { useAuth } from "../../lib/auth/auth-context";
import { useActionError } from "../../lib/mutations/action-error";

type AnalystTaskDetailProps = {
  task: AnalystTask | undefined;
  onTaskChange: (task: AnalystTask) => void;
};

const EMPTY_SEARCH: StoreSearchResponse = {
  products: [],
  total: 0,
  page: 1,
  pageSize: 0,
  totalPages: 0,
  facets: { productTypes: [], regions: [], tags: [] },
};
const ACTIVE_ANALYST_STATES = new Set(["ANALYST_IN_PROGRESS", "REWORK_REQUIRED"]);

export default function AnalystTaskDetail({ onTaskChange, task }: AnalystTaskDetailProps) {
  const { session } = useAuth();
  const csrfToken = session?.csrfToken ?? "";
  const [noteBody, setNoteBody] = useState("");
  const [productQuery, setProductQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [draft, setDraft] = useState({
    title: "",
    summary: "",
    productType: "finished_output",
    content: "",
    assetName: "assessment-draft.pdf",
  });
  const productsQuery = useQuery({
    queryKey: ["analyst-product-search", submittedQuery],
    queryFn: () => searchStoreProducts({ query: submittedQuery }),
    enabled: submittedQuery.trim().length > 0,
    placeholderData: EMPTY_SEARCH,
    retry: false,
  });
  const { actionError, clearActionError, failActionWith } = useActionError();
  const noteMutation = useMutation({
    mutationFn: ({ body, ticketId }: { body: string; ticketId: string }) =>
      addAnalystNote(ticketId, body, csrfToken),
    onError: failActionWith("The note could not be added. Try again."),
    onMutate: clearActionError,
    onSuccess: (nextTask) => {
      setNoteBody("");
      onTaskChange(nextTask);
    },
  });
  const linkMutation = useMutation({
    mutationFn: ({ productId, ticketId }: { productId: string; ticketId: string }) =>
      linkAnalystProduct(ticketId, productId, csrfToken),
    onError: failActionWith("The product could not be linked. Try again."),
    onMutate: clearActionError,
    onSuccess: onTaskChange,
  });
  const packageMutation = useMutation({
    mutationFn: ({ packageId, ticketId }: { packageId: string; ticketId: string }) =>
      updateWorkPackage(ticketId, packageId, "complete", csrfToken),
    onError: failActionWith("The work package could not be updated. Try again."),
    onMutate: clearActionError,
    onSuccess: onTaskChange,
  });
  const draftMutation = useMutation({
    mutationFn: ({ ticketId }: { ticketId: string }) =>
      saveDraftProduct(
        ticketId,
        {
          title: draft.title,
          summary: draft.summary,
          productType: draft.productType,
          content: draft.content,
          assets: draft.assetName.trim()
            ? [
                {
                  name: draft.assetName,
                  assetType: "pdf",
                  mimeType: "application/pdf",
                  sizeBytes: 512,
                  sha256: "e".repeat(64),
                },
              ]
            : [],
        },
        csrfToken,
      ),
    onError: failActionWith("The draft could not be saved. Try again."),
    onMutate: clearActionError,
    onSuccess: (nextTask) => {
      setDraft((current) => ({ ...current, title: "", summary: "", content: "" }));
      onTaskChange(nextTask);
    },
  });
  const submitMutation = useMutation({
    mutationFn: ({ ticketId }: { ticketId: string }) => submitTaskToQc(ticketId, csrfToken),
    onError: failActionWith("The task could not be submitted to QC. Try again."),
    onMutate: clearActionError,
    onSuccess: onTaskChange,
  });

  if (!task) {
    return (
      <section className="surface analyst-detail" aria-label="Analyst task detail">
        <p>No assigned task selected.</p>
      </section>
    );
  }

  const canSubmit =
    ACTIVE_ANALYST_STATES.has(task.state) &&
    task.drafts.length > 0 &&
    task.workPackages.every((item) => item.status === "complete");

  return (
    <section className="surface analyst-detail" aria-label="Analyst task detail">
      <div className="section-heading">
        <h2>{task.reference}</h2>
        <p>{task.title}</p>
      </div>
      {actionError ? (
        <p className="auth-error" role="alert">
          {actionError}
        </p>
      ) : null}
      <AnalystTaskContext task={task} />
      <section className="analyst-panel">
        <h3>Work packages</h3>
        {task.workPackages.map((item) => (
          <label className="analyst-check" key={item.id}>
            <input
              checked={item.status === "complete"}
              disabled={item.status === "complete" || !ACTIVE_ANALYST_STATES.has(task.state)}
              onChange={() =>
                packageMutation.mutate({ packageId: item.id, ticketId: task.ticketId })
              }
              type="checkbox"
            />
            <span>{item.title}</span>
          </label>
        ))}
      </section>
      <details className="workspace-details">
        <summary>
          <StickyNote aria-hidden="true" size={16} />
          Working notes ({task.notes.length})
        </summary>
        <section className="analyst-panel">
          <form
            className="analyst-inline-form"
            onSubmit={(event) => {
              event.preventDefault();
              noteMutation.mutate({ body: noteBody, ticketId: task.ticketId });
            }}
          >
            <label>
              Note
              <textarea onChange={(event) => setNoteBody(event.target.value)} value={noteBody} />
            </label>
            <button disabled={noteBody.trim().length < 3} type="submit">
              Add note
            </button>
          </form>
          <ul className="analyst-list-items">
            {task.notes.map((note) => (
              <li key={note.id}>{note.body}</li>
            ))}
          </ul>
        </section>
      </details>
      <details className="workspace-details">
        <summary>
          <Link2 aria-hidden="true" size={16} />
          Linked products ({task.linkedProducts.length})
        </summary>
        <section className="analyst-panel">
          <form
            className="analyst-inline-form"
            onSubmit={(event) => {
              event.preventDefault();
              setSubmittedQuery(productQuery.trim());
            }}
          >
            <label>
              Product search
              <input
                onChange={(event) => setProductQuery(event.target.value)}
                value={productQuery}
              />
            </label>
            <button disabled={productQuery.trim().length < 2} type="submit">
              Search products
            </button>
          </form>
          <div className="analyst-product-results">
            {productsQuery.isError ? (
              <div className="workspace-alert" role="alert">
                <span>Product search could not be loaded.</span>
                <button onClick={() => void productsQuery.refetch()} type="button">
                  Retry product search
                </button>
              </div>
            ) : null}
            {(productsQuery.data?.products ?? []).map((product) => (
              <button
                key={product.id}
                onClick={() =>
                  linkMutation.mutate({ productId: product.id, ticketId: task.ticketId })
                }
                type="button"
              >
                {product.title}
              </button>
            ))}
          </div>
          <ul className="analyst-list-items">
            {task.linkedProducts.map((product) => (
              <li key={product.id}>
                <strong>{product.reference}</strong> {product.title}
              </li>
            ))}
          </ul>
        </section>
      </details>
      <section className="analyst-panel">
        <h3>Draft product</h3>
        <AnalystDraftForm
          draft={draft}
          onChange={setDraft}
          onSubmit={() => draftMutation.mutate({ ticketId: task.ticketId })}
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
        disabled={!canSubmit || submitMutation.isPending}
        onClick={() => submitMutation.mutate({ ticketId: task.ticketId })}
        type="button"
      >
        Submit to QC
      </button>
    </section>
  );
}
