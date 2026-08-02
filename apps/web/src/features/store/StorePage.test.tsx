import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import StorePage from "./StorePage";
import { collectionProduct, visibleProduct } from "./store-page.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/auth";
import { renderWithProviders } from "../../test/test-utils";

const searchField = "Search the Intelligence Store";

async function searchFor(term: string) {
  await userEvent.type(await screen.findByLabelText(searchField), term);
  await userEvent.click(screen.getByRole("button", { name: "Search" }));
}

function facets(counts: Record<string, Record<string, number>> = {}) {
  return {
    productTypes: Object.keys(counts.productTypes ?? {}),
    regions: Object.keys(counts.regions ?? {}),
    tags: Object.keys(counts.tags ?? {}),
    counts: { productTypes: {}, regions: {}, tags: {}, ...counts },
  };
}

function respondWith(payload: Record<string, unknown>) {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ facets: facets(), relaxed: false, ...payload }),
  });
}

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders visible store products and facets only from authorised results", async () => {
  vi.stubGlobal(
    "fetch",
    respondWith({
      products: [visibleProduct],
      total: 1,
      facets: facets({ productTypes: { assessment_report: 1 } }),
    }),
  );

  renderWithProviders(<StorePage />, "/store");

  expect(await screen.findByRole("heading", { name: "Intelligence Store" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Back to Admin" })).toHaveAttribute(
    "href",
    "/admin/overview",
  );
  // Nothing is listed until the user searches.
  expect(screen.getByText("Search the Intelligence Store", { selector: "h2" })).toBeVisible();
  expect(screen.queryByText("Regional Stability Brief")).not.toBeInTheDocument();
  await searchFor("regional");
  expect(await screen.findByText("Regional Stability Brief")).toBeVisible();
  const refine = screen.getByRole("complementary", { name: "Refine results" });
  expect(within(refine).getByRole("button", { name: /Assessment report/ })).toBeVisible();
});

test("keeps the applied search in the URL so it survives navigation", async () => {
  const fetchMock = respondWith({ products: [visibleProduct], total: 1 });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<StorePage />, "/store");
  await screen.findByRole("heading", { name: "Intelligence Store" });
  await userEvent.selectOptions(screen.getByLabelText("Product type"), "assessment_report");
  await userEvent.type(screen.getByLabelText(searchField), "harbour");
  await userEvent.type(screen.getByLabelText("Region"), "Baltic");
  await userEvent.type(screen.getByLabelText("Tag"), "regional");
  await userEvent.type(screen.getByLabelText("Source type"), "finished_assessment");
  await userEvent.type(screen.getByLabelText("Coverage from"), "2026-05-01");
  await userEvent.type(screen.getByLabelText("Coverage to"), "2026-06-30");
  await userEvent.click(screen.getByRole("button", { name: "Search" }));

  await screen.findByText("Regional Stability Brief");
  const calls = fetchMock.mock.calls as Array<[string, RequestInit]>;
  const [url, init] = calls[calls.length - 1];
  expect(url).toContain("query=harbour");
  expect(url).toContain("productType=assessment_report");
  expect(url).toContain("region=Baltic");
  expect(url).toContain("tag=regional");
  expect(url).toContain("sourceType=finished_assessment");
  expect(url).toContain("dateFrom=2026-05-01");
  expect(url).toContain("dateTo=2026-06-30");
  expect(url).toContain("page=1");
  expect(url).toContain("pageSize=24");
  expect(url).toContain("sort=relevance");
  expect(init.credentials).toBe("include");
});

test("sorting and paging ask the server rather than reordering one page", async () => {
  const fetchMock = respondWith({
    products: [visibleProduct],
    total: 60,
    page: 1,
    pageSize: 24,
    totalPages: 3,
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<StorePage />, "/store");

  await searchFor("brief");
  expect(await screen.findByText("Showing 1-24 of 60")).toBeVisible();

  await userEvent.selectOptions(screen.getByLabelText("Sort by"), "coverage");
  await screen.findByText("Regional Stability Brief");
  expect(lastUrl(fetchMock)).toContain("sort=coverage");

  await userEvent.click(screen.getByRole("button", { name: "Page 3" }));
  await screen.findByText("Regional Stability Brief");
  expect(lastUrl(fetchMock)).toContain("page=3");
});

test("clicking a facet applies it as a filter and clicking again removes it", async () => {
  const fetchMock = respondWith({
    products: [visibleProduct],
    total: 1,
    facets: facets({ regions: { "Baltic ports": 4 } }),
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<StorePage />, "/store");
  await searchFor("brief");

  const facetButton = await screen.findByRole("button", { name: /Baltic ports/ });
  expect(facetButton).toHaveAttribute("aria-pressed", "false");

  await userEvent.click(facetButton);
  await screen.findByText("Regional Stability Brief");
  expect(lastUrl(fetchMock)).toContain("region=Baltic+ports");
  expect(screen.getByRole("button", { name: /Baltic ports/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  // Clicking the applied facet clears it. The unfiltered search is already
  // cached, so assert the applied state rather than expecting a new request.
  await userEvent.click(screen.getByRole("button", { name: /Baltic ports/ }));
  expect(await screen.findByText("Regional Stability Brief")).toBeVisible();
  expect(screen.getByRole("button", { name: /Baltic ports/ })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
});

test("clears every refinement at once while keeping the search term", async () => {
  const fetchMock = respondWith({
    products: [visibleProduct],
    total: 1,
    facets: facets({
      regions: { "Baltic ports": 4 },
      productTypes: { assessment_report: 2 },
    }),
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<StorePage />, "/store");
  await searchFor("brief");

  await userEvent.click(await screen.findByRole("button", { name: /Baltic ports/ }));
  await screen.findByText("Regional Stability Brief");
  await userEvent.click(await screen.findByRole("button", { name: /Assessment report/ }));
  await screen.findByText("Regional Stability Brief");

  await userEvent.click(screen.getByRole("button", { name: "Clear" }));
  await screen.findByText("Regional Stability Brief");

  expect(screen.getByRole("button", { name: /Baltic ports/ })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  expect(screen.getByRole("button", { name: /Assessment report/ })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  expect(screen.queryByRole("button", { name: "Clear" })).not.toBeInTheDocument();
  // The term the operator typed is not a refinement, so it survives.
  expect(screen.getByLabelText(searchField)).toHaveValue("brief");
});

test("facet counts show only while they describe the results on screen", async () => {
  // Refinement options ignore the search term so a narrow query still leaves
  // somewhere to go, which means their counts describe the catalogue. Showing
  // "136" beside "12 products" would read as a contradiction.
  const fetchMock = respondWith({
    products: [visibleProduct],
    total: 12,
    facets: facets({ productTypes: { assessment_report: 136 } }),
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<StorePage />, "/store?type=assessment_report");

  const browsing = await screen.findByRole("button", { name: /Assessment report/ });
  expect(browsing).toHaveTextContent("136");
  expect(screen.getByText(/Counts cover every product/)).toBeVisible();

  await userEvent.type(screen.getByLabelText(searchField), "donbas");
  await userEvent.click(screen.getByRole("button", { name: "Search" }));

  const searching = await screen.findByRole("button", { name: /Assessment report/ });
  expect(searching).not.toHaveTextContent("136");
  expect(screen.getByText(/Narrow these results further/)).toBeVisible();
});

test("a facet click applies the current search, not unsubmitted filter edits", async () => {
  // Facets act on what is applied. A half-typed advanced filter is not applied
  // by a facet click, so the draft resets to the applied search rather than
  // sending a partial value to the server.
  const fetchMock = respondWith({
    products: [visibleProduct],
    total: 1,
    facets: facets({ regions: { "Baltic ports": 4 } }),
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<StorePage />, "/store");
  await searchFor("brief");
  await userEvent.type(screen.getByLabelText("Source type"), "finished_ass");

  await userEvent.click(await screen.findByRole("button", { name: /Baltic ports/ }));
  await screen.findByText("Regional Stability Brief");

  expect(lastUrl(fetchMock)).not.toContain("sourceType");
  expect(screen.getByLabelText("Source type")).toHaveValue("");
});

test("says so when the search was broadened to close matches", async () => {
  vi.stubGlobal("fetch", respondWith({ products: [collectionProduct], total: 1, relaxed: true }));

  renderWithProviders(<StorePage />, "/store");
  await searchFor("arctic shipping routes");

  expect(
    await screen.findByText(
      "No products match all of your terms. Showing the closest matches instead.",
    ),
  ).toBeVisible();
});

test("explains a bookmarked page that the result set no longer has", async () => {
  // The server echoes the requested page with an empty product list, which is
  // not the same as nothing matching.
  const fetchMock = respondWith({
    products: [],
    total: 17,
    page: 3,
    pageSize: 24,
    totalPages: 1,
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<StorePage />, "/store?q=baltic&page=3");

  expect(await screen.findByText("Page 3 is past the end of these 17 results.")).toBeVisible();
  expect(screen.queryByText("No products match this search")).not.toBeInTheDocument();
  expect(screen.queryByText(/Showing 49/)).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Back to the first page" }));
  expect(lastUrl(fetchMock)).toContain("page=1");
});

test("renders a store search error state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );

  renderWithProviders(<StorePage />, "/store");

  await searchFor("anything");
  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
});

test("hints when a search is submitted with no criteria", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<StorePage />, "/store");

  await screen.findByText("Search the Intelligence Store", { selector: "h2" });
  await userEvent.click(screen.getByRole("button", { name: "Search" }));

  expect(
    await screen.findByText("Enter a search term or pick at least one filter first."),
  ).toBeVisible();
  expect(fetchMock).not.toHaveBeenCalled();
});

test("catalogue curators still browse without searching", async () => {
  const curatorSession: AuthSession = {
    csrfToken: "test-csrf-token",
    user: {
      id: "curator-user",
      username: "store.manager@example.test",
      displayName: "Store Curator",
      roles: ["Intelligence Store Manager"],
      defaultRoute: "/store",
      passwordResetRequired: false,
      permissions: ["product:read", "product:search", "store:browse_all"],
    },
  };
  vi.stubGlobal("fetch", respondWith({ products: [visibleProduct], total: 1 }));

  renderWithProviders(<StorePage />, "/store", curatorSession);

  expect(await screen.findByText("Regional Stability Brief")).toBeVisible();
  expect(
    screen.queryByText("Search the Intelligence Store", { selector: "h2" }),
  ).not.toBeInTheDocument();
});

function lastUrl(fetchMock: ReturnType<typeof vi.fn>) {
  const calls = fetchMock.mock.calls as Array<[string, RequestInit]>;
  return calls[calls.length - 1][0];
}
