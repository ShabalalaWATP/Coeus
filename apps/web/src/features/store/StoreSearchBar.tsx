import { Search, SlidersHorizontal } from "lucide-react";
import { useId } from "react";

import { productTypeOptions } from "./store-options";
import type { StoreSearchState } from "./store-search-params";

type StoreSearchBarProps = {
  draft: StoreSearchState;
  hint: string | null;
  onChange: (draft: StoreSearchState) => void;
  onSubmit: () => void;
  refinedCount: number;
};

export function StoreSearchBar({
  draft,
  hint,
  onChange,
  onSubmit,
  refinedCount,
}: StoreSearchBarProps) {
  const queryId = useId();
  const update = (field: keyof StoreSearchState, value: string) => {
    onChange({ ...draft, [field]: value });
  };
  return (
    <form
      className="store-searchbar"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="store-searchbar__row">
        <label className="store-searchbar__field" htmlFor={queryId}>
          <Search aria-hidden="true" size={18} />
          <span className="sr-only">Search the Intelligence Store</span>
          <input
            autoComplete="off"
            id={queryId}
            onChange={(event) => update("query", event.target.value)}
            placeholder="Search by subject, region, title or tag"
            value={draft.query}
          />
        </label>
        <button className="store-action" type="submit">
          Search
        </button>
      </div>

      <details className="store-searchbar__advanced">
        <summary>
          <SlidersHorizontal aria-hidden="true" size={15} />
          Advanced filters
          {refinedCount > 0 ? <span className="store-chip">{refinedCount} applied</span> : null}
        </summary>
        <div className="store-searchbar__grid">
          <label>
            Product type
            <select
              onChange={(event) => update("productType", event.target.value)}
              value={draft.productType}
            >
              <option value="">Any type</option>
              {productTypeOptions.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Source type
            <input
              onChange={(event) => update("sourceType", event.target.value)}
              value={draft.sourceType}
            />
          </label>
          <label>
            Region
            <input
              onChange={(event) => update("region", event.target.value)}
              value={draft.region}
            />
          </label>
          <label>
            Tag
            <input onChange={(event) => update("tag", event.target.value)} value={draft.tag} />
          </label>
          <label>
            Coverage from
            <input
              onChange={(event) => update("dateFrom", event.target.value)}
              type="date"
              value={draft.dateFrom}
            />
          </label>
          <label>
            Coverage to
            <input
              onChange={(event) => update("dateTo", event.target.value)}
              type="date"
              value={draft.dateTo}
            />
          </label>
        </div>
      </details>

      {hint !== null ? (
        <p className="store-searchbar__hint" role="alert">
          {hint}
        </p>
      ) : null}
    </form>
  );
}
