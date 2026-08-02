import { SlidersHorizontal, X } from "lucide-react";

import { productTypeLabel, visibleProductTags } from "./store-options";
import type { StoreSearchState } from "./store-search-params";
import type { StoreSearchResponse } from "../../lib/api-client/store";

type FacetField = "productType" | "region" | "tag";

type StoreFacetRailProps = {
  facets: StoreSearchResponse["facets"];
  onClear: () => void;
  onToggle: (field: FacetField, value: string) => void;
  state: StoreSearchState;
};

const MAX_FACET_OPTIONS = 8;

export function StoreFacetRail({ facets, onClear, onToggle, state }: StoreFacetRailProps) {
  // Refinement options are deliberately computed without the search term, so a
  // narrow query still leaves somewhere to go. That makes their counts describe
  // the catalogue rather than the results on screen, which would read as a
  // contradiction next to the result total, so counts are shown only while they
  // do describe those results.
  const showCounts = state.query === "";
  const options = (values: string[], counts: Record<string, number>) =>
    values.map((value) => ({ value, count: showCounts ? (counts[value] ?? 0) : null }));
  const tagOptions = options(facets.tags, facets.counts.tags).filter(
    // Internal provenance tags are never operational refinements.
    (option) => visibleProductTags([option.value]).length === 1,
  );
  const hasRefinement = state.productType !== "" || state.region !== "" || state.tag !== "";
  return (
    <aside className="store-refine" aria-label="Refine results">
      <div className="store-refine__head">
        <h2>
          <SlidersHorizontal aria-hidden="true" size={15} />
          Refine
        </h2>
        {hasRefinement ? (
          <button className="store-refine__clear" onClick={onClear} type="button">
            <X aria-hidden="true" size={14} />
            Clear
          </button>
        ) : null}
      </div>

      <FacetGroup
        active={state.productType}
        field="productType"
        format={productTypeLabel}
        onToggle={onToggle}
        options={options(facets.productTypes, facets.counts.productTypes)}
        title="Product type"
      />
      <FacetGroup
        active={state.region}
        field="region"
        onToggle={onToggle}
        options={options(facets.regions, facets.counts.regions)}
        title="Region"
      />
      <FacetGroup
        active={state.tag}
        field="tag"
        onToggle={onToggle}
        options={tagOptions}
        title="Tag"
      />
      <p className="store-refine__note">
        {showCounts
          ? "Counts cover every product you are cleared to see for this search."
          : "Narrow these results further. Options cover the holdings you are cleared to see."}
      </p>
    </aside>
  );
}

function FacetGroup({
  active,
  field,
  format = (value: string) => value,
  onToggle,
  options,
  title,
}: {
  active: string;
  field: FacetField;
  format?: (value: string) => string;
  onToggle: (field: FacetField, value: string) => void;
  options: { count: number | null; value: string }[];
  title: string;
}) {
  // Keep the active choice visible even when it falls outside the top options.
  const top = options.slice(0, MAX_FACET_OPTIONS);
  const visible = top.some((option) => option.value === active)
    ? top
    : [...options.filter((option) => option.value === active), ...top].slice(0, MAX_FACET_OPTIONS);
  if (visible.length === 0) {
    return null;
  }
  return (
    <section className="store-refine__group">
      <h3>{title}</h3>
      <ul>
        {visible.map((option) => (
          <li key={option.value}>
            <button
              aria-pressed={option.value === active}
              className="store-refine__option"
              onClick={() => onToggle(field, option.value)}
              type="button"
            >
              <span>{format(option.value)}</span>
              {option.count === null ? null : (
                <span className="store-refine__count">{option.count}</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
