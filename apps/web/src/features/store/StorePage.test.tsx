import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import StorePage from "./StorePage";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/client";
import { renderWithProviders } from "../../test/test-utils";

const visibleProduct = {
  id: "product-regional",
  reference: "PROD-1001",
  title: "Regional Stability Brief",
  summary: "MOCK DATA ONLY assessment summary",
  description: "Synthetic detail",
  productType: "assessment_report",
  sourceType: "finished_assessment",
  ownerTeam: "RFA",
  areaOrRegion: "Baltic ports",
  classificationLevel: 2,
  releasability: ["MOCK"],
  handlingCaveats: ["MOCK DATA ONLY"],
  tags: ["regional"],
  acgIds: ["acg-alpha"],
  projectId: "project-northstar",
  status: "published",
  timePeriodStart: null,
  timePeriodEnd: null,
  geojsonRef: null,
  assets: [],
  matchScore: 1,
  matchReasons: ["visible"],
};

const collectionProduct = {
  ...visibleProduct,
  id: "product-collection",
  title: "Collection Sensor Summary",
  productType: "unmapped_type",
  ownerTeam: "Collection",
  areaOrRegion: "North Sea",
  timePeriodStart: "2026-05-01",
};

const readOnlyCollectionSession: AuthSession = {
  csrfToken: "test-csrf-token",
  user: {
    id: "collection-user",
    username: "collection@example.test",
    displayName: "Collection User",
    roles: ["Collection Manager"],
    defaultRoute: "/store",
    permissions: ["product:read", "product:search"],
  },
};

const rfaManagerSession: AuthSession = {
  csrfToken: "test-csrf-token",
  user: {
    id: "rfa-user",
    username: "rfa.manager@example.test",
    displayName: "RFA Manager",
    roles: ["Request for Assessment Manager"],
    defaultRoute: "/rfa/queue",
    permissions: ["product:read", "product:search"],
  },
};

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
  expect(await screen.findByText("Regional Stability Brief")).toBeVisible();
  expect(screen.queryByText("Collection Sensor Summary")).not.toBeInTheDocument();
  expect(
    within(screen.getByLabelText("Visible facets")).getByText("Assessment report"),
  ).toBeVisible();
});

test("submits product search filters", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [],
          total: 0,
          facets: { productTypes: [], regions: [], tags: [] },
        }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [visibleProduct],
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
  expect(init.credentials).toBe("include");
});

test("filters my products by owner team and hides upload without create permission", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [visibleProduct, collectionProduct],
          total: 2,
          facets: { productTypes: [], regions: [], tags: [] },
        }),
    }),
  );

  renderWithProviders(<StorePage scope="mine" />, "/store/my-products", readOnlyCollectionSession);

  expect(await screen.findByRole("heading", { name: "My Products" })).toBeVisible();
  expect(await screen.findByText("Collection Sensor Summary")).toBeVisible();
  expect(screen.getByText("2026-05-01 to ongoing")).toBeVisible();
  expect(screen.queryByText("Regional Stability Brief")).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Upload product" })).not.toBeInTheDocument();
  expect(screen.getByText("MOCK DATA ONLY")).toBeVisible();
});

test("scopes my products to the RFA team for an assessment manager", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [visibleProduct, collectionProduct],
          total: 2,
          facets: { productTypes: [], regions: [], tags: [] },
        }),
    }),
  );

  renderWithProviders(<StorePage scope="mine" />, "/store/my-products", rfaManagerSession);

  expect(await screen.findByText("Regional Stability Brief")).toBeVisible();
  expect(screen.queryByText("Collection Sensor Summary")).not.toBeInTheDocument();
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

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
});

test("filters team product workspaces by explicit owner team", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [visibleProduct, collectionProduct],
          total: 2,
          facets: { productTypes: [], regions: [], tags: [] },
        }),
    }),
  );

  renderWithProviders(
    <StorePage
      description="Request for Assessment product workspace."
      ownerTeam="RFA"
      title="RFA Products"
    />,
    "/rfa/products",
  );

  expect(await screen.findByRole("heading", { name: "RFA Products" })).toBeVisible();
  expect(await screen.findByText("Regional Stability Brief")).toBeVisible();
  expect(screen.queryByText("Collection Sensor Summary")).not.toBeInTheDocument();
});
