import { Link2, StickyNote } from "lucide-react";
import type { FormEvent } from "react";

import type { AnalystTask } from "../../lib/api-client/analyst";
import type { StoreProduct } from "../../lib/api-client/store";
import { ACTIVE_ANALYST_STATES } from "./analyst-task-policy";

export function WorkPackagesPanel({
  onComplete,
  task,
}: {
  onComplete: (packageId: string) => void;
  task: AnalystTask;
}) {
  return (
    <section className="analyst-panel">
      <h3>Work packages</h3>
      {task.workPackages.map((item) => (
        <label className="analyst-check" key={item.id}>
          <input
            checked={item.status === "complete"}
            disabled={item.status === "complete" || !ACTIVE_ANALYST_STATES.has(task.state)}
            onChange={() => onComplete(item.id)}
            type="checkbox"
          />
          <span>{item.title}</span>
        </label>
      ))}
    </section>
  );
}

export function NotesPanel({
  noteBody,
  onNoteChange,
  onSubmit,
  task,
}: {
  noteBody: string;
  onNoteChange: (body: string) => void;
  onSubmit: () => void;
  task: AnalystTask;
}) {
  return (
    <details className="workspace-details">
      <summary>
        <StickyNote aria-hidden="true" size={16} />
        Working notes ({task.notes.length})
      </summary>
      <section className="analyst-panel">
        <form className="analyst-inline-form" onSubmit={(event) => submit(event, onSubmit)}>
          <label>
            Note
            <textarea onChange={(event) => onNoteChange(event.target.value)} value={noteBody} />
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
  );
}

export function LinkedProductsPanel({
  isError,
  onLink,
  onQueryChange,
  onRetry,
  onSearch,
  products,
  productQuery,
  task,
}: {
  isError: boolean;
  onLink: (productId: string) => void;
  onQueryChange: (query: string) => void;
  onRetry: () => void;
  onSearch: () => void;
  products: StoreProduct[];
  productQuery: string;
  task: AnalystTask;
}) {
  return (
    <details className="workspace-details">
      <summary>
        <Link2 aria-hidden="true" size={16} />
        Linked products ({task.linkedProducts.length})
      </summary>
      <section className="analyst-panel">
        <form className="analyst-inline-form" onSubmit={(event) => submit(event, onSearch)}>
          <label>
            Product search
            <input onChange={(event) => onQueryChange(event.target.value)} value={productQuery} />
          </label>
          <button disabled={productQuery.trim().length < 2} type="submit">
            Search products
          </button>
        </form>
        <div className="analyst-product-results">
          {isError ? (
            <div className="workspace-alert" role="alert">
              <span>Product search could not be loaded.</span>
              <button onClick={onRetry} type="button">
                Retry product search
              </button>
            </div>
          ) : null}
          {products.map((product) => (
            <button key={product.id} onClick={() => onLink(product.id)} type="button">
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
  );
}

function submit(event: FormEvent, action: () => void) {
  event.preventDefault();
  action();
}
