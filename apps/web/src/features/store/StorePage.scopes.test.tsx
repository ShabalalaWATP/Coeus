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

function respondWith(products: unknown[], total = products.length) {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        products,
        total,
        facets: {
          productTypes: [],
          regions: [],
          tags: [],
          counts: { productTypes: {}, regions: {}, tags: {} },
        },
        relaxed: false,
      }),
  });
}

function lastUrl(fetchMock: ReturnType<typeof vi.fn>) {
  const calls = fetchMock.mock.calls as Array<[string, RequestInit]>;
  return calls[calls.length - 1][0];
}

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("scopes my products to the owner team server-side and hides upload without create permission", async () => {
  // Owner-team scoping is enforced by the API in SQL and rechecked in the
  // service, so the page asks for the scope rather than filtering a page of
  // results locally, which used to make totals and pagination disagree.
  const fetchMock = respondWith([collectionProduct]);
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<StorePage scope="mine" />, "/store/my-products", readOnlyCollectionSession);

  expect(await screen.findByRole("heading", { name: "My Products" })).toBeVisible();
  expect(await screen.findByText("Collection Sensor Summary")).toBeVisible();
  expect(screen.getByText("From 1 May 2026")).toBeVisible();
  expect(lastUrl(fetchMock)).toContain("ownerTeam=Collection");
  expect(screen.queryByRole("link", { name: "Upload product" })).not.toBeInTheDocument();
  expect(screen.queryByText("MOCK DATA ONLY")).not.toBeInTheDocument();
});

test("scopes my products to the RFA team for an assessment manager", async () => {
  const fetchMock = respondWith([visibleProduct]);
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<StorePage scope="mine" />, "/store/my-products", rfaManagerSession);

  expect(await screen.findByText("Regional Stability Brief")).toBeVisible();
  expect(lastUrl(fetchMock)).toContain("ownerTeam=RFA");
});

test("a role with no owner team is guided instead of shown the whole catalogue", async () => {
  const adminSession: AuthSession = {
    csrfToken: "test-csrf-token",
    user: {
      id: "admin-user",
      username: "admin@example.test",
      displayName: "Administrator",
      roles: ["Administrator"],
      defaultRoute: "/admin/overview",
      passwordResetRequired: false,
      permissions: ["product:read", "product:search", "store:browse_all"],
    },
  };
  const fetchMock = respondWith([visibleProduct, collectionProduct], 8);
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<StorePage scope="mine" />, "/store/my-products", adminSession);

  expect(await screen.findByRole("heading", { name: "My Products" })).toBeVisible();
  expect(await screen.findByText(/My Products is for RFA and Collection teams/)).toBeVisible();
  expect(screen.queryByText("Regional Stability Brief")).not.toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalledWith(
    expect.stringContaining("/store/products"),
    expect.anything(),
  );
});

test("filters team product workspaces by explicit owner team", async () => {
  const fetchMock = respondWith([visibleProduct]);
  vi.stubGlobal("fetch", fetchMock);

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
  expect(lastUrl(fetchMock)).toContain("ownerTeam=RFA");
});
