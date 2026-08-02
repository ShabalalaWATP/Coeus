import { pageWindow } from "./store-page-window";

type PaginationSummaryProps = {
  page: number;
  pageSize: number;
  total: number;
};

export function PaginationSummary({ page, pageSize, total }: PaginationSummaryProps) {
  if (total === 0) {
    return <p className="store-page-summary">No products to show.</p>;
  }
  const start = (page - 1) * pageSize + 1;
  // A page past the end has no range to describe; the results area explains it.
  if (start > total) {
    return null;
  }
  const end = Math.min(total, page * pageSize);
  return (
    <p className="store-page-summary">
      Showing {start}-{end} of {total}
    </p>
  );
}

type PaginationControlsProps = {
  onSelect: (page: number) => void;
  page: number;
  totalPages: number;
};

export function PaginationControls({ onSelect, page, totalPages }: PaginationControlsProps) {
  // Comparisons against a non-numeric total silently pass, so check the value
  // is usable rather than only that it is greater than one.
  if (!Number.isInteger(totalPages) || totalPages <= 1) {
    return null;
  }
  return (
    <nav className="store-pagination" aria-label="Store pages">
      <button disabled={page <= 1} onClick={() => onSelect(page - 1)} type="button">
        Previous page
      </button>
      <ol className="store-pagination__pages">
        {pageWindow(page, totalPages).map((entry, index) =>
          entry === null ? (
            <li aria-hidden="true" className="store-pagination__gap" key={`gap-${index}`}>
              …
            </li>
          ) : (
            <li key={entry}>
              <button
                aria-current={entry === page ? "page" : undefined}
                aria-label={`Page ${entry}`}
                onClick={() => onSelect(entry)}
                type="button"
              >
                {entry}
              </button>
            </li>
          ),
        )}
      </ol>
      <button disabled={page >= totalPages} onClick={() => onSelect(page + 1)} type="button">
        Next page
      </button>
    </nav>
  );
}
