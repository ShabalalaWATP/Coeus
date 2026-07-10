import { Search, SlidersHorizontal } from "lucide-react";
import type { Dispatch, SetStateAction } from "react";

import { productTypeOptions } from "./store-options";

export type StoreFilterDraft = {
  query: string;
  productType: string;
  region: string;
  tag: string;
  sourceType: string;
  dateFrom: string;
  dateTo: string;
};

type StoreSearchFiltersPanelProps = {
  filters: StoreFilterDraft;
  onFiltersChange: Dispatch<SetStateAction<StoreFilterDraft>>;
  onSubmit: (filters: StoreFilterDraft) => void;
};

export function StoreSearchFiltersPanel({
  filters,
  onFiltersChange,
  onSubmit,
}: StoreSearchFiltersPanelProps) {
  const updateFilter = (field: keyof StoreFilterDraft, value: string) => {
    onFiltersChange((current) => ({ ...current, [field]: value }));
  };
  return (
    <details className="workspace-details store-search" open>
      <summary>
        <SlidersHorizontal aria-hidden="true" size={16} />
        Search and filters
      </summary>
      <form
        className="surface store-filters"
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(filters);
        }}
      >
        <p className="store-filters__note">Filters run after ACG and classification checks.</p>
        <label>
          Full text
          <input
            onChange={(event) => updateFilter("query", event.target.value)}
            placeholder="Search title, summary, tags"
            value={filters.query}
          />
        </label>
        <label>
          Product type
          <select
            onChange={(event) => updateFilter("productType", event.target.value)}
            value={filters.productType}
          >
            <option value="">Any type</option>
            {productTypeOptions.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <div className="store-filter-grid">
          <label>
            Region
            <input
              onChange={(event) => updateFilter("region", event.target.value)}
              value={filters.region}
            />
          </label>
          <label>
            Tag
            <input
              onChange={(event) => updateFilter("tag", event.target.value)}
              value={filters.tag}
            />
          </label>
        </div>
        <label>
          Source type
          <input
            onChange={(event) => updateFilter("sourceType", event.target.value)}
            value={filters.sourceType}
          />
        </label>
        <div className="store-filter-grid">
          <label>
            Coverage from
            <input
              onChange={(event) => updateFilter("dateFrom", event.target.value)}
              type="date"
              value={filters.dateFrom}
            />
          </label>
          <label>
            Coverage to
            <input
              onChange={(event) => updateFilter("dateTo", event.target.value)}
              type="date"
              value={filters.dateTo}
            />
          </label>
        </div>
        <button type="submit">
          <Search aria-hidden="true" size={18} />
          Search products
        </button>
      </form>
    </details>
  );
}
