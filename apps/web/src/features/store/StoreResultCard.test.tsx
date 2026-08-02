import { screen } from "@testing-library/react";

import { StoreResultCard } from "./StoreResultCard";
import { visibleProduct } from "./store-page.fixtures";
import { renderWithProviders } from "../../test/test-utils";

type Product = Parameters<typeof StoreResultCard>[0]["product"];

function card(overrides: Partial<Product> = {}, showMatchReasons = false) {
  const product = { ...visibleProduct, ...overrides } as Product;
  return renderWithProviders(
    <StoreResultCard product={product} showMatchReasons={showMatchReasons} />,
    "/store",
  );
}

test("marks classification and links to the product", () => {
  card({ classificationLevel: 4 });

  expect(screen.getByText("Class 4")).toBeVisible();
  expect(screen.getByRole("link")).toHaveAttribute("href", "/store/products/product-regional");
  expect(screen.getByText("PROD-1001")).toBeVisible();
});

test("badges a product that is not yet published", () => {
  const { unmount } = card({ status: "draft" });
  expect(screen.getByText("draft")).toBeVisible();
  unmount();

  card({ status: "published" });
  expect(screen.queryByText("published")).not.toBeInTheDocument();
});

test("states coverage in plain dates and admits when there is none", () => {
  const { unmount } = card({ timePeriodStart: "2026-05-01", timePeriodEnd: "2026-06-20" });
  expect(screen.getByText("1 May to 20 Jun 2026")).toBeVisible();
  unmount();

  card({ timePeriodStart: null, timePeriodEnd: null });
  expect(screen.getByText("Not recorded")).toBeVisible();
});

test("says what the product contains, and omits the row when it holds nothing", () => {
  const { unmount } = card({
    assets: [
      {
        id: "asset-1",
        name: "brief.pdf",
        assetType: "pdf",
        mimeType: "application/pdf",
        sizeBytes: 2048,
        sha256: "a".repeat(64),
        previewKind: "pdf_metadata",
      },
    ],
  });
  expect(screen.getByText("Contains")).toBeVisible();
  expect(screen.getByText("PDF")).toBeVisible();
  unmount();

  card({ assets: [] });
  expect(screen.queryByText("Contains")).not.toBeInTheDocument();
});

test("shows operational tags but never internal provenance tags", () => {
  const { unmount } = card({ tags: ["ports", "mock-data", "synthetic-exercise"] });
  expect(screen.getByText("ports")).toBeVisible();
  expect(screen.queryByText("mock-data")).not.toBeInTheDocument();
  unmount();

  card({ tags: ["mock"] });
  expect(screen.queryByText("mock")).not.toBeInTheDocument();
});

test("explains the match only once a query has been run", () => {
  const { unmount } = card({ matchReasons: ["full-text:harbour"] }, true);
  expect(screen.getByText("Matched harbour")).toBeVisible();
  unmount();

  card({ matchReasons: ["full-text:harbour"] }, false);
  expect(screen.queryByText("Matched harbour")).not.toBeInTheDocument();
});

test("survives a product with no match reasons at all", () => {
  card({ matchReasons: undefined }, true);

  expect(screen.getByText("Regional Stability Brief")).toBeVisible();
});
