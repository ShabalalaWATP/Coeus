import { ApiError } from "./client";
import { downloadAssetBlob } from "./store";

afterEach(() => {
  vi.restoreAllMocks();
});

test("downloads assets with the token in the X-Asset-Token header", async () => {
  const blob = new Blob(["mock"]);
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    blob: () => Promise.resolve(blob),
  });
  vi.stubGlobal("fetch", fetchMock);

  await expect(downloadAssetBlob("product/one", "asset two", "token/value")).resolves.toBe(blob);

  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/store/products/product%2Fone/assets/asset%20two/download",
    {
      cache: "no-store",
      credentials: "include",
      headers: { "X-Asset-Token": "token/value" },
      method: "GET",
    },
  );
});

test("throws a typed error when the asset download is rejected", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      blob: () => Promise.resolve(new Blob()),
    }),
  );

  await expect(downloadAssetBlob("product-1", "asset-1", "expired")).rejects.toEqual(
    new ApiError(403, "request_failed", "API request failed with status 403"),
  );
});
