import { assetDownloadUrl } from "./store";

test("encodes product and asset identifiers in download URLs", () => {
  expect(assetDownloadUrl("product/one", "asset two", "token/value")).toBe(
    "http://127.0.0.1:8001/api/v1/store/products/product%2Fone/assets/asset%20two/download?token=token%2Fvalue",
  );
});
