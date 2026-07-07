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
  const end = Math.min(total, page * pageSize);
  return (
    <p className="store-page-summary">
      Showing {start}-{end} of {total}
    </p>
  );
}

type PaginationControlsProps = {
  onNext: () => void;
  onPrevious: () => void;
  page: number;
  totalPages: number;
};

export function PaginationControls({
  onNext,
  onPrevious,
  page,
  totalPages,
}: PaginationControlsProps) {
  if (totalPages <= 1) {
    return null;
  }
  return (
    <nav className="store-pagination" aria-label="Store pages">
      <button disabled={page <= 1} onClick={onPrevious} type="button">
        Previous page
      </button>
      <span>
        Page {page} of {totalPages}
      </span>
      <button disabled={page >= totalPages} onClick={onNext} type="button">
        Next page
      </button>
    </nav>
  );
}
