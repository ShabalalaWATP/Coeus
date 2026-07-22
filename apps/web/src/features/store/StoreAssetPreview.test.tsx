import { screen, waitFor } from "@testing-library/react";

import { StoreAssetPreview } from "./StoreAssetPreview";
import { getQueryClient, resetQueryClientForTests } from "../../app/query-client";
import { previewStoreAssetBlob, type StoreAsset } from "../../lib/api-client/store";
import { renderWithProviders } from "../../test/test-utils";

vi.mock("../../lib/api-client/store", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api-client/store")>()),
  previewStoreAssetBlob: vi.fn(),
}));

const asset: StoreAsset = {
  id: "asset-1",
  name: "assessment.docx",
  assetType: "docx",
  mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  sizeBytes: 100,
  sha256: "a".repeat(64),
  previewKind: "text",
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
  Reflect.deleteProperty(URL, "createObjectURL");
  Reflect.deleteProperty(URL, "revokeObjectURL");
});

test("waits for an access grant before requesting a controlled preview", () => {
  renderWithProviders(<StoreAssetPreview asset={asset} productId="product-1" />);

  expect(screen.getByText("Preparing controlled preview…")).toBeVisible();
  expect(previewStoreAssetBlob).not.toHaveBeenCalled();
});

test("shows a safe fallback when preview generation fails", async () => {
  vi.mocked(previewStoreAssetBlob).mockRejectedValue(new Error("preview unavailable"));
  renderWithProviders(
    <StoreAssetPreview
      asset={asset}
      grant={{ assetId: asset.id, downloadToken: "token-123", expiresInSeconds: 60 }}
      productId="product-1"
    />,
  );

  expect(
    await screen.findByText("A safe inline preview is not available for this file."),
  ).toBeVisible();
});

test("does not expose a blob when the browser cannot create object URLs", async () => {
  vi.mocked(previewStoreAssetBlob).mockResolvedValue(new Blob(["preview"]));
  renderWithProviders(
    <StoreAssetPreview
      asset={asset}
      grant={{ assetId: asset.id, downloadToken: "token-123", expiresInSeconds: 60 }}
      productId="product-1"
    />,
  );

  expect(await screen.findByText("Preparing controlled preview…")).toBeVisible();
  await waitFor(() => expect(previewStoreAssetBlob).toHaveBeenCalled());
});

test("releases a preview safely when URL revocation is unavailable", async () => {
  vi.mocked(previewStoreAssetBlob).mockResolvedValue(new Blob(["preview"]));
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:controlled-preview"),
  });
  const rendered = renderWithProviders(
    <StoreAssetPreview
      asset={asset}
      grant={{ assetId: asset.id, downloadToken: "token-123", expiresInSeconds: 60 }}
      productId="product-1"
    />,
  );

  expect(await screen.findByTitle("assessment.docx")).toHaveAttribute(
    "src",
    "blob:controlled-preview",
  );
  expect(JSON.stringify(getQueryClient().getQueryCache().getAll())).not.toContain("token-123");
  rendered.unmount();
});
