import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ProductDetailPage from "./ProductDetailPage";
import { backNavigationFor } from "./store-navigation";
import { productFixture as product } from "./store-test-fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import type { Permission } from "../../lib/api-client/auth";
import { previewSession, renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders product metadata and asset list", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(product) }),
  );

  renderWithProviders(<ProductDetailPage />, "/store/products/product-regional");

  expect(await screen.findByRole("heading", { name: "Regional Stability Brief" })).toBeVisible();
  expect(screen.getByText("Assessment report")).toBeVisible();
  expect(screen.getByText("maritime")).toBeVisible();
  expect(screen.getByText("regional-brief.pdf")).toBeVisible();
});

test("renders controlled asset denial without exposing object storage", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(product) })
      .mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ error: { code: "asset_not_found", message: "Not found." } }),
      }),
  );

  renderWithProviders(<ProductDetailPage />, "/store/products/product-regional/assets/asset-brief");

  expect(await screen.findByText("Asset access denied or unavailable.")).toBeVisible();
  expect(screen.queryByText("objectKey")).not.toBeInTheDocument();
});

test("uses the originating workspace for back navigation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(product) }),
  );

  renderWithProviders(<ProductDetailPage />, "/store/products/product-regional", null, {
    from: "/rfa/products",
  });

  expect(await screen.findByRole("link", { name: /Back to products/ })).toHaveAttribute(
    "href",
    "/rfa/products",
  );
});

test("maps back navigation targets from the originating workspace", () => {
  expect(backNavigationFor(undefined)).toEqual({ path: "/store", label: "Back to store" });
  expect(backNavigationFor("/store")).toEqual({ path: "/store", label: "Back to store" });
  expect(backNavigationFor("/rfa/products")).toEqual({
    path: "/rfa/products",
    label: "Back to products",
  });
});

test("renders denied page without leaking product metadata", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: { code: "product_not_found", message: "Not found." } }),
    }),
  );

  renderWithProviders(<ProductDetailPage />, "/store/products/product-hidden");

  expect(await screen.findByRole("heading", { name: "Product not available" })).toBeVisible();
  expect(screen.queryByText("Regional Stability Brief")).not.toBeInTheDocument();
});

test("renders a retryable error state for product lookup failures", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: false,
    status: 500,
    json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ProductDetailPage />, "/store/products/product-regional");

  expect(await screen.findByText("Unable to load data")).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Product not available" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));

  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test("allows audited break-glass access for restricted-read administrators", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: { code: "product_not_found", message: "Not found." } }),
    })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(product) });
  vi.stubGlobal("fetch", fetchMock);
  const session = {
    ...previewSession,
    user: {
      ...previewSession.user,
      permissions: [
        ...previewSession.user.permissions,
        "product:read_restricted",
      ] satisfies Permission[],
    },
  };

  renderWithProviders(<ProductDetailPage />, "/store/products/product-hidden", session);

  await userEvent.type(
    await screen.findByLabelText("Emergency support reason"),
    "Synthetic support incident requiring audited access.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Access with audit log" }));

  expect(await screen.findByRole("heading", { name: "Regional Stability Brief" })).toBeVisible();
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/store/products/product-hidden/break-glass",
    expect.objectContaining({
      body: JSON.stringify({ reason: "Synthetic support incident requiring audited access." }),
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": "test-csrf-token",
      },
      method: "POST",
    }),
  );
});

test("makes assets selectable after audited break-glass product access", async () => {
  const hiddenProduct = { ...product, id: "product-hidden" };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: { code: "product_not_found", message: "Not found." } }),
    })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(hiddenProduct) });
  vi.stubGlobal("fetch", fetchMock);
  const session = {
    ...previewSession,
    user: {
      ...previewSession.user,
      permissions: [
        ...previewSession.user.permissions.filter(
          (permission) => permission !== "product:download",
        ),
        "product:read_restricted",
      ] satisfies Permission[],
    },
  };

  renderWithProviders(<ProductDetailPage />, "/store/products/product-hidden", session);

  await userEvent.type(
    await screen.findByLabelText("Emergency support reason"),
    "Synthetic support incident requiring audited access.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Access with audit log" }));

  const assetLink = await screen.findByRole("link", { name: /regional-brief\.pdf/ });
  expect(assetLink).toHaveAttribute("href", "/store/products/product-hidden/assets/asset-brief");
  expect(
    screen.queryByText("You do not have permission to download assets. Metadata remains visible."),
  ).not.toBeInTheDocument();
});

test("uses audited break-glass grants for hidden asset downloads", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: { code: "product_not_found", message: "Not found." } }),
    })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(product) })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          assetId: "asset-brief",
          downloadToken: "asset-token-break-glass",
          expiresInSeconds: 900,
        }),
    });
  vi.stubGlobal("fetch", fetchMock);
  const session = {
    ...previewSession,
    user: {
      ...previewSession.user,
      permissions: [
        ...previewSession.user.permissions,
        "product:read_restricted",
      ] satisfies Permission[],
    },
  };

  renderWithProviders(
    <ProductDetailPage />,
    "/store/products/product-hidden/assets/asset-brief",
    session,
  );

  await userEvent.type(
    await screen.findByLabelText("Emergency support reason"),
    "Synthetic support incident requiring audited asset access.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Access with audit log" }));

  expect(await screen.findByRole("button", { name: "Download asset" })).toBeVisible();
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/store/products/product-hidden/assets/asset-brief/break-glass-access",
    expect.objectContaining({
      body: JSON.stringify({
        reason: "Synthetic support incident requiring audited asset access.",
      }),
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": "test-csrf-token",
      },
      method: "POST",
    }),
  );
});
