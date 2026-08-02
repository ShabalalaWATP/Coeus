import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  hasSearchCriteria,
  readStoreSearch,
  toSearchRequest,
  writeStoreSearch,
  type StoreSearchState,
} from "./store-search-params";
import { searchStoreProducts, type StoreSearchResponse } from "../../lib/api-client/store";

const emptySearch: StoreSearchResponse = {
  products: [],
  total: 0,
  page: 1,
  pageSize: 0,
  totalPages: 0,
  facets: {
    productTypes: [],
    regions: [],
    tags: [],
    counts: { productTypes: {}, regions: {}, tags: {} },
  },
  relaxed: false,
};

type UseStoreSearchOptions = {
  canBrowseAll: boolean;
  /** False when the page itself has no valid scope to search within. */
  canSearch?: boolean;
  ownerTeam?: string;
};

/**
 * Drive Store search from the URL.
 *
 * Keeping applied search state in the address bar is what makes a result set
 * survivable: it can be shared, refreshed, bookmarked, and returned to with the
 * browser Back button after opening a product.
 */
export function useStoreSearch({
  canBrowseAll,
  canSearch = true,
  ownerTeam,
}: UseStoreSearchOptions) {
  const [searchParams, setSearchParams] = useSearchParams();
  const applied = useMemo(() => readStoreSearch(searchParams), [searchParams]);
  const [draft, setDraft] = useState(applied);
  const [hint, setHint] = useState<string | null>(null);
  const appliedKey = writeStoreSearch(applied).toString();

  // Facet clicks and browser history both change the URL without going through
  // the search bar, so the draft follows whatever is currently applied.
  useEffect(() => {
    setDraft(readStoreSearch(new URLSearchParams(appliedKey)));
  }, [appliedKey]);

  const enabled =
    canSearch && (ownerTeam !== undefined || canBrowseAll || hasSearchCriteria(applied));
  const request = useMemo(() => toSearchRequest(applied, ownerTeam), [applied, ownerTeam]);
  const query = useQuery({
    enabled,
    queryKey: ["store-products", request],
    queryFn: () => searchStoreProducts(request),
    placeholderData: (previous) => previous ?? emptySearch,
  });

  const apply = (next: StoreSearchState) => {
    if (ownerTeam === undefined && !canBrowseAll && !hasSearchCriteria(next)) {
      setHint("Enter a search term or pick at least one filter first.");
      return;
    }
    setHint(null);
    setSearchParams(writeStoreSearch(next), { replace: false });
  };

  return {
    applied,
    apply,
    data: query.data ?? emptySearch,
    draft,
    enabled,
    hint,
    isError: query.isError,
    isFetching: query.isFetching,
    refetch: () => void query.refetch(),
    setDraft,
  };
}
