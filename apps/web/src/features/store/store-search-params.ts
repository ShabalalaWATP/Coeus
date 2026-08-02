import type { StoreSearchFilters } from "../../lib/api-client/store";

type StoreSort = "relevance" | "title" | "coverage";

export type StoreSearchState = {
  query: string;
  productType: string;
  region: string;
  tag: string;
  sourceType: string;
  dateFrom: string;
  dateTo: string;
  sort: StoreSort;
  page: number;
};

const STORE_PAGE_SIZE = 24;

// Short, readable URL keys: a store search is meant to be pasted into a ticket
// or a message, so the address bar has to stay legible.
const PARAM_KEYS = {
  query: "q",
  productType: "type",
  region: "region",
  tag: "tag",
  sourceType: "source",
  dateFrom: "from",
  dateTo: "to",
} as const;

type TextField = keyof typeof PARAM_KEYS;

const TEXT_FIELDS = Object.keys(PARAM_KEYS) as TextField[];
const SORTS: readonly StoreSort[] = ["relevance", "title", "coverage"];

const emptyStoreSearch: StoreSearchState = {
  query: "",
  productType: "",
  region: "",
  tag: "",
  sourceType: "",
  dateFrom: "",
  dateTo: "",
  sort: "relevance",
  page: 1,
};

export function readStoreSearch(params: URLSearchParams): StoreSearchState {
  const state = { ...emptyStoreSearch };
  for (const field of TEXT_FIELDS) {
    state[field] = (params.get(PARAM_KEYS[field]) ?? "").trim();
  }
  const sort = params.get("sort");
  if (isSort(sort)) {
    state.sort = sort;
  }
  state.page = readPage(params.get("page"));
  return state;
}

export function writeStoreSearch(state: StoreSearchState): URLSearchParams {
  const params = new URLSearchParams();
  for (const field of TEXT_FIELDS) {
    const value = state[field].trim();
    if (value !== "") {
      params.set(PARAM_KEYS[field], value);
    }
  }
  if (state.sort !== "relevance") {
    params.set("sort", state.sort);
  }
  if (state.page > 1) {
    params.set("page", String(state.page));
  }
  return params;
}

export function hasSearchCriteria(state: StoreSearchState): boolean {
  return TEXT_FIELDS.some((field) => state[field].trim() !== "");
}

export function toSearchRequest(state: StoreSearchState, ownerTeam?: string): StoreSearchFilters {
  return {
    ...(state.query ? { query: state.query } : {}),
    ...(state.productType ? { productType: state.productType } : {}),
    ...(state.region ? { region: state.region } : {}),
    ...(state.tag ? { tag: state.tag } : {}),
    ...(state.sourceType ? { sourceType: state.sourceType } : {}),
    ...(state.dateFrom ? { dateFrom: state.dateFrom } : {}),
    ...(state.dateTo ? { dateTo: state.dateTo } : {}),
    ...(ownerTeam ? { ownerTeam } : {}),
    sort: state.sort,
    page: state.page,
    pageSize: STORE_PAGE_SIZE,
  };
}

/** Toggle a facet value off when it is already the active filter. */
export function toggleFacet(
  state: StoreSearchState,
  field: "productType" | "region" | "tag",
  value: string,
): StoreSearchState {
  return {
    ...state,
    [field]: state[field] === value ? "" : value,
    page: 1,
  };
}

export function activeFilterCount(state: StoreSearchState): number {
  return TEXT_FIELDS.filter((field) => field !== "query" && state[field].trim() !== "").length;
}

function isSort(value: string | null): value is StoreSort {
  return value !== null && (SORTS as readonly string[]).includes(value);
}

function readPage(value: string | null): number {
  const page = Number(value);
  return Number.isInteger(page) && page > 0 ? page : 1;
}
