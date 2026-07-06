import { screen } from "@testing-library/react";

import ProductDetailPage from "./ProductDetailPage";
import { backNavigationFor } from "./store-navigation";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const product = {
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
  tags: ["regional", "ports"],
  acgIds: ["acg-alpha"],
  projectId: "project-northstar",
  status: "published",
  timePeriodStart: null,
  timePeriodEnd: null,
  geojsonRef: null,
  assets: [
    {
      id: "asset-brief",
      name: "regional-brief.pdf",
      assetType: "pdf",
      mimeType: "application/pdf",
      sizeBytes: 12000,
      sha256: "b".repeat(64),
      previewKind: "pdf_metadata",
    },
  ],
};

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
  expect(screen.getByText("regional-brief.pdf")).toBeVisible();
});

test("renders controlled asset grant for selected asset route", async () => {
  vi.stubGlobal(
    "fetch",
    vi
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
      }),
  );

  renderWithProviders(<ProductDetailPage />, "/store/products/product-regional/assets/asset-brief");

  expect(await screen.findByText("asset-token-asset-brief")).toBeVisible();
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

test("maps back navigation targets from the originating workspace", () => {
  expect(backNavigationFor(undefined)).toEqual({ path: "/store", label: "Back to store" });
  expect(backNavigationFor("/store")).toEqual({ path: "/store", label: "Back to store" });
  expect(backNavigationFor("/projects/project-1/products")).toEqual({
    path: "/projects/project-1/products",
    label: "Back to project",
  });
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
