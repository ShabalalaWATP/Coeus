import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import StorePage from "./StorePage";
import { collectionProduct, visibleProduct } from "./store-page.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/auth";
import { renderWithProviders } from "../../test/test-utils";

async function searchFor(term: string) {
  await userEvent.type(await screen.findByLabelText("Full text"), term);
  await userEvent.click(screen.getByRole("button", { name: "Search products" }));
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
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [visibleProduct],
          total: 1,
          facets: { productTypes: ["assessment_report"], regions: ["Baltic ports"], tags: [] },
        }),
    }),
  );

  renderWithProviders(<StorePage />, "/store");

  expect(await screen.findByRole("heading", { name: "Intelligence Store" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Back to Admin" })).toHaveAttribute(
    "href",
    "/admin/overview",
  );
  // Nothing is listed until the user searches.
  expect(screen.getByText("Search the Intelligence Store")).toBeVisible();
  expect(screen.queryByText("Regional Stability Brief")).not.toBeInTheDocument();
  await searchFor("regional");
  expect(await screen.findByText("Regional Stability Brief")).toBeVisible();
  expect(screen.queryByText("Collection Sensor Summary")).not.toBeInTheDocument();
  expect(
    within(screen.getByLabelText("Visible facets")).getByText("Assessment report"),
  ).toBeVisible();
});

test("submits product search filters", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        products: [
          {
            ...visibleProduct,
            matchReasons: ["lexical-rank:1", "vector-similarity:0.82", "full-text:harbour"],
          },
        ],
        total: 1,
        facets: { productTypes: [], regions: [], tags: [] },
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<StorePage />, "/store");
  await screen.findByRole("heading", { name: "Intelligence Store" });
  await userEvent.selectOptions(screen.getByLabelText("Product type"), "assessment_report");
  await userEvent.type(screen.getByLabelText("Full text"), "harbour");
  await userEvent.type(screen.getByLabelText("Region"), "Baltic");
  await userEvent.type(screen.getByLabelText("Tag"), "regional");
  await userEvent.type(screen.getByLabelText("Source type"), "finished_assessment");
  await userEvent.type(screen.getByLabelText("Coverage from"), "2026-05-01");
  await userEvent.type(screen.getByLabelText("Coverage to"), "2026-06-30");
  await userEvent.click(screen.getByRole("button", { name: "Search products" }));

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
  expect(url).toContain("pageSize=6");
  expect(init.credentials).toBe("include");
  expect(await screen.findByText("Why it matched")).toBeVisible();
  expect(screen.getByText("Text rank 1")).toBeVisible();
  expect(screen.getByText("Semantic 82%")).toBeVisible();
  expect(screen.getByText("Term harbour")).toBeVisible();
});

test("requests the next store result page", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [visibleProduct],
          total: 8,
          page: 1,
          pageSize: 6,
          totalPages: 2,
          facets: { productTypes: [], regions: [], tags: [] },
        }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [collectionProduct],
          total: 8,
          page: 2,
          pageSize: 6,
          totalPages: 2,
          facets: { productTypes: [], regions: [], tags: [] },
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<StorePage />, "/store");

  await searchFor("brief");
  expect(await screen.findByText("Showing 1-6 of 8")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Next page" }));

  expect(await screen.findByText("Collection Sensor Summary")).toBeVisible();
  const calls = fetchMock.mock.calls as Array<[string, RequestInit]>;
  expect(calls[calls.length - 1][0]).toContain("page=2");
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

  await screen.findByText("Search the Intelligence Store");
  await userEvent.click(screen.getByRole("button", { name: "Search products" }));

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
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [visibleProduct],
          total: 1,
          facets: { productTypes: [], regions: [], tags: [] },
        }),
    }),
  );

  renderWithProviders(<StorePage />, "/store", curatorSession);

  expect(await screen.findByText("Regional Stability Brief")).toBeVisible();
  expect(screen.queryByText("Search the Intelligence Store")).not.toBeInTheDocument();
});
