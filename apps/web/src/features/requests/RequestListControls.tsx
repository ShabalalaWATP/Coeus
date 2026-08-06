import { ListFilter } from "lucide-react";

import { REQUEST_SORTS, type RequestSort } from "./ticket-collection";

export type RequestFilter = "all" | "action" | "draft" | "progress" | "closed";

type FilterOption = { value: RequestFilter; label: string; count: number };

type RequestListControlsProps = {
  filter: RequestFilter;
  onFilterChange: (filter: RequestFilter) => void;
  onSortChange: (sort: RequestSort) => void;
  options: FilterOption[];
  sort: RequestSort;
};

export function RequestListControls({
  filter,
  onFilterChange,
  onSortChange,
  options,
  sort,
}: RequestListControlsProps) {
  return (
    <div className="request-controls">
      <div className="request-controls__filters" role="group" aria-label="Filter requests">
        <ListFilter aria-hidden="true" size={16} />
        {options.map((option) => (
          <button
            aria-pressed={filter === option.value}
            className="request-controls__filter"
            disabled={option.count === 0 && option.value !== "all"}
            key={option.value}
            onClick={() => onFilterChange(option.value)}
            type="button"
          >
            {option.label}
            <span className="request-controls__count">{option.count}</span>
          </button>
        ))}
      </div>
      <label className="request-controls__sort" htmlFor="request-sort">
        Sort by
        <select
          id="request-sort"
          onChange={(event) => onSortChange(event.target.value as RequestSort)}
          value={sort}
        >
          {REQUEST_SORTS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
