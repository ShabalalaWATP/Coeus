import { useMutation, useQuery } from "@tanstack/react-query";
import { Link2, StickyNote } from "lucide-react";
import { useState } from "react";

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
  });
  const noteMutation = useMutation({
    mutationFn: ({ body, ticketId }: { body: string; ticketId: string }) =>
      addAnalystNote(ticketId, body, csrfToken),
    onSuccess: (nextTask) => {
      setNoteBody("");
      onTaskChange(nextTask);
    },
  });
  const linkMutation = useMutation({
    mutationFn: ({ productId, ticketId }: { productId: string; ticketId: string }) =>
      linkAnalystProduct(ticketId, productId, csrfToken),
    onSuccess: onTaskChange,
  });
  const packageMutation = useMutation({
    mutationFn: ({ packageId, ticketId }: { packageId: string; ticketId: string }) =>
      updateWorkPackage(ticketId, packageId, "complete", csrfToken),
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
    onSuccess: (nextTask) => {
      setDraft((current) => ({ ...current, title: "", summary: "", content: "" }));
      onTaskChange(nextTask);
    },
  });
  const submitMutation = useMutation({
    mutationFn: ({ ticketId }: { ticketId: string }) => submitTaskToQc(ticketId, csrfToken),
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
      <TaskContext task={task} />
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
        <DraftForm
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

function TaskContext({ task }: { task: AnalystTask }) {
  return (
    <section className="analyst-context">
      <dl>
        <div>
          <dt>State</dt>
          <dd>{task.state.replaceAll("_", " ")}</dd>
        </div>
        <div>
          <dt>Region</dt>
          <dd>{task.areaOrRegion ?? "Not set"}</dd>
        </div>
        <div>
          <dt>Output</dt>
          <dd>{task.requiredOutputFormat ?? "Not set"}</dd>
        </div>
        <div>
          <dt>Team</dt>
          <dd>{task.assignment?.teamName ?? "Not assigned"}</dd>
        </div>
      </dl>
      <p>{task.description}</p>
      <ul>
        {task.managerNotes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </section>
  );
}

function DraftForm({
  draft,
  onChange,
  onSubmit,
}: {
  draft: {
    title: string;
    summary: string;
    productType: string;
    content: string;
    assetName: string;
  };
  onChange: (draft: {
    title: string;
    summary: string;
    productType: string;
    content: string;
    assetName: string;
  }) => void;
  onSubmit: () => void;
}) {
  const canSave = draft.title.trim() && draft.summary.trim() && draft.content.trim().length >= 10;
  return (
    <form
      className="analyst-draft-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <label>
        Title
        <input
          onChange={(event) => onChange({ ...draft, title: event.target.value })}
          value={draft.title}
        />
      </label>
      <label>
        Summary
        <input
          onChange={(event) => onChange({ ...draft, summary: event.target.value })}
          value={draft.summary}
        />
      </label>
      <label>
        Content
        <textarea
          onChange={(event) => onChange({ ...draft, content: event.target.value })}
          value={draft.content}
        />
      </label>
      <label>
        Asset name
        <input
          onChange={(event) => onChange({ ...draft, assetName: event.target.value })}
          value={draft.assetName}
        />
      </label>
      <button disabled={!canSave} type="submit">
        Save draft
      </button>
    </form>
  );
}
