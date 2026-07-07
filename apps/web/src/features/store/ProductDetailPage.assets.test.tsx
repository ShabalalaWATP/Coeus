import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ProductDetailPage from "./ProductDetailPage";
import { productFixture as product, stubObjectUrls } from "./store-test-fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { previewSession, renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
  Reflect.deleteProperty(URL, "createObjectURL");
  Reflect.deleteProperty(URL, "revokeObjectURL");
});

test("downloads a granted asset with the token in a request header", async () => {
  const assetBlob = new Blob(["mock"]);
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(product) })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          assetId: "asset-brief",
          downloadToken: "asset-token-asset-brief",
          expiresInSeconds: 900,
        }),
    })
    .mockResolvedValueOnce({ ok: true, blob: () => Promise.resolve(assetBlob) });
  vi.stubGlobal("fetch", fetchMock);
  const { createObjectURL, revokeObjectURL } = stubObjectUrls();
  const anchorClick = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => undefined);

  renderWithProviders(<ProductDetailPage />, "/store/products/product-regional/assets/asset-brief");

  await userEvent.click(await screen.findByRole("button", { name: "Download asset" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/store/products/product-regional/assets/asset-brief/download",
    {
      cache: "no-store",
      credentials: "include",
      headers: { "X-Asset-Token": "asset-token-asset-brief" },
      method: "GET",
    },
  );
  expect(createObjectURL).toHaveBeenCalledWith(assetBlob);
  expect(anchorClick).toHaveBeenCalledTimes(1);
  expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock-asset");
});

test("shows a visible message when the asset download fails", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(product) })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          assetId: "asset-brief",
          downloadToken: "asset-token-asset-brief",
          expiresInSeconds: 900,
        }),
    })
    .mockResolvedValueOnce({ ok: false, status: 403, blob: () => Promise.resolve(new Blob()) });
  vi.stubGlobal("fetch", fetchMock);
  stubObjectUrls();

  renderWithProviders(<ProductDetailPage />, "/store/products/product-regional/assets/asset-brief");

  await userEvent.click(await screen.findByRole("button", { name: "Download asset" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The asset could not be downloaded. Request access again and retry.",
  );
});

test("renders assets without links for users who cannot download", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(product) }),
  );
  const session = {
    ...previewSession,
    user: {
      ...previewSession.user,
      permissions: previewSession.user.permissions.filter(
        (permission) => permission !== "product:download",
      ),
    },
  };

  renderWithProviders(<ProductDetailPage />, "/store/products/product-regional", session);

  expect(await screen.findByText("regional-brief.pdf")).toBeVisible();
  expect(
    screen.getByText("You do not have permission to download assets. Metadata remains visible."),
  ).toBeVisible();
  expect(screen.queryByRole("link", { name: /regional-brief/ })).not.toBeInTheDocument();
});

test("keeps the originating workspace when opening an asset", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(product) })
      .mockResolvedValue({
        ok: true,
        json: () =>
          Promise.resolve({
            assetId: "asset-brief",
            downloadToken: "asset-token-asset-brief",
            expiresInSeconds: 900,
          }),
      }),
  );

  renderWithProviders(<ProductDetailPage />, "/store/products/product-regional", previewSession, {
    from: "/rfa/products",
  });

  await userEvent.click(await screen.findByRole("link", { name: /regional-brief\.pdf/ }));

  expect(await screen.findByRole("button", { name: "Download asset" })).toBeVisible();
  expect(screen.getByRole("link", { name: /Back to products/ })).toHaveAttribute(
    "href",
    "/rfa/products",
  );
});
