import { screen } from "@testing-library/react";

import StorePage from "./StorePage";
import {
  collectionProduct,
  readOnlyCollectionSession,
  rfaManagerSession,
  visibleProduct,
} from "./store-page.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/auth";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
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

test("keeps counts and pagination consistent when the mine scope filters client-side", async () => {
  const adminSession: AuthSession = {
    csrfToken: "test-csrf-token",
    user: {
      id: "admin-user",
      username: "admin@example.test",
      displayName: "Administrator",
      roles: ["Administrator"],
      defaultRoute: "/admin/overview",
      passwordResetRequired: false,
      permissions: ["product:read", "product:search"],
    },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          products: [visibleProduct, collectionProduct],
          total: 8,
          page: 1,
          pageSize: 6,
          totalPages: 2,
          facets: { productTypes: [], regions: [], tags: [] },
        }),
    }),
  );

  const fetchMock = window.fetch as ReturnType<typeof vi.fn>;

  renderWithProviders(<StorePage scope="mine" />, "/store/my-products", adminSession);

  expect(await screen.findByRole("heading", { name: "My Products" })).toBeVisible();
  // Roles with no owner team get the guidance alert and no product fetch:
  // the store no longer lists holdings without a scope or search.
  expect(await screen.findByText(/My Products is for RFA and Collection teams/)).toBeVisible();
  expect(screen.queryByText("Regional Stability Brief")).not.toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalledWith(
    expect.stringContaining("/store/products"),
    expect.anything(),
  );
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
