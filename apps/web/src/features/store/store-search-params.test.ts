import {
  activeFilterCount,
  hasSearchCriteria,
  readStoreSearch,
  toSearchRequest,
  toggleFacet,
  writeStoreSearch,
} from "./store-search-params";
import type { StoreSearchState } from "./store-search-params";

const STORE_PAGE_SIZE = 24;
const emptyStoreSearch: StoreSearchState = {
  acgIds: [],
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

test("reads a full search from the URL", () => {
  const state = readStoreSearch(
    new URLSearchParams(
      "acg=one&acg=two&q=arctic&type=assessment_report&region=Baltic&tag=ports&source=sensor&from=2026-01-01&to=2026-06-30&sort=title&page=3",
    ),
  );

  expect(state).toEqual({
    acgIds: ["one", "two"],
    query: "arctic",
    productType: "assessment_report",
    region: "Baltic",
    tag: "ports",
    sourceType: "sensor",
    dateFrom: "2026-01-01",
    dateTo: "2026-06-30",
    sort: "title",
    page: 3,
  });
});

test("falls back to safe defaults for missing or invalid parameters", () => {
  expect(readStoreSearch(new URLSearchParams())).toEqual(emptyStoreSearch);
  expect(readStoreSearch(new URLSearchParams("sort=sideways")).sort).toBe("relevance");
  expect(readStoreSearch(new URLSearchParams("page=0")).page).toBe(1);
  expect(readStoreSearch(new URLSearchParams("page=-2")).page).toBe(1);
  expect(readStoreSearch(new URLSearchParams("page=two")).page).toBe(1);
  expect(readStoreSearch(new URLSearchParams("page=1.5")).page).toBe(1);
  expect(readStoreSearch(new URLSearchParams("q=  arctic  ")).query).toBe("arctic");
  expect(readStoreSearch(new URLSearchParams("acg=one&acg=one&acg=two")).acgIds).toEqual([
    "one",
    "two",
  ]);
});

test("writes only the parameters that carry meaning", () => {
  expect(writeStoreSearch(emptyStoreSearch).toString()).toBe("");
  expect(
    writeStoreSearch({ ...emptyStoreSearch, query: "arctic", sort: "relevance" }).toString(),
  ).toBe("q=arctic");
  expect(writeStoreSearch({ ...emptyStoreSearch, sort: "coverage", page: 4 }).toString()).toBe(
    "sort=coverage&page=4",
  );
  expect(writeStoreSearch({ ...emptyStoreSearch, acgIds: ["one", "two"] }).toString()).toBe(
    "acg=one&acg=two",
  );
});

test("a written search reads back unchanged", () => {
  const state = {
    ...emptyStoreSearch,
    query: "arctic ice",
    region: "Arctic Circle",
    sort: "coverage" as const,
    page: 2,
  };

  expect(readStoreSearch(writeStoreSearch(state))).toEqual(state);
});

test("recognises when a search has a criterion beyond pagination", () => {
  expect(hasSearchCriteria(emptyStoreSearch)).toBe(false);
  expect(hasSearchCriteria({ ...emptyStoreSearch, page: 4, sort: "title" })).toBe(false);
  expect(hasSearchCriteria({ ...emptyStoreSearch, tag: "ports" })).toBe(true);
  expect(hasSearchCriteria({ ...emptyStoreSearch, acgIds: ["one"] })).toBe(true);
});

test("builds a request with only the filters that were set", () => {
  expect(toSearchRequest({ ...emptyStoreSearch, query: "arctic", page: 2 })).toEqual({
    query: "arctic",
    sort: "relevance",
    page: 2,
    pageSize: STORE_PAGE_SIZE,
  });
  expect(toSearchRequest(emptyStoreSearch, "RFA")).toEqual({
    ownerTeam: "RFA",
    sort: "relevance",
    page: 1,
    pageSize: STORE_PAGE_SIZE,
  });
  expect(toSearchRequest({ ...emptyStoreSearch, acgIds: ["one"] })).toEqual({
    acgIds: ["one"],
    sort: "relevance",
    page: 1,
    pageSize: STORE_PAGE_SIZE,
  });
});

test("toggling a facet applies it, and toggling the same value clears it", () => {
  const applied = toggleFacet({ ...emptyStoreSearch, page: 5 }, "region", "Arctic Circle");
  expect(applied.region).toBe("Arctic Circle");
  // A new refinement invalidates the page the user was on.
  expect(applied.page).toBe(1);

  expect(toggleFacet(applied, "region", "Arctic Circle").region).toBe("");
  expect(toggleFacet(applied, "region", "Baltic ports").region).toBe("Baltic ports");
});

test("counts applied refinements without counting the search term", () => {
  expect(activeFilterCount({ ...emptyStoreSearch, query: "arctic" })).toBe(0);
  expect(activeFilterCount({ ...emptyStoreSearch, region: "Baltic", tag: "ports" })).toBe(2);
  expect(activeFilterCount({ ...emptyStoreSearch, acgIds: ["one"] })).toBe(1);
});
