import { screen } from "@testing-library/react";

import { ProductAssets, ProductDenied, ProductMetadata } from "./ProductDetailSections";
import { productFixture } from "./store-test-fixtures";
import type { StoreProduct } from "../../lib/api-client/store";
import { renderWithProviders } from "../../test/test-utils";

const product = productFixture as StoreProduct;

test("renders ongoing and bounded coverage with sparse handling metadata", () => {
  const { rerender } = renderWithProviders(
    <ProductMetadata
      product={{
        ...product,
        timePeriodStart: "2026-08-01",
        timePeriodEnd: null,
        releasability: [],
        handlingCaveats: [],
        geojsonRef: "synthetic-layer",
      }}
    />,
    "/store/products/product-regional",
  );

  expect(screen.getByText("2026-08-01 to ongoing")).toBeInTheDocument();
  expect(screen.getByText("None")).toBeInTheDocument();
  expect(screen.getAllByText("Not recorded")).toHaveLength(1);
  expect(screen.getByText("Geospatial layer")).toBeInTheDocument();

  rerender(
    <ProductMetadata
      product={{ ...product, timePeriodStart: "2026-08-01", timePeriodEnd: "2026-08-02" }}
    />,
  );
  expect(screen.getByText("2026-08-01 to 2026-08-02")).toBeInTheDocument();
});

test("keeps an unknown requested asset inside the controlled grant boundary", () => {
  renderWithProviders(
    <ProductAssets
      accessStatus="success"
      assetId="missing-asset"
      canRequestAccess
      from="/store"
      product={product}
    />,
    "/store/products/product-regional/assets/missing-asset",
  );

  expect(screen.getByText("regional-brief.pdf")).toBeVisible();
  expect(screen.getByText("Preparing controlled access")).toBeVisible();
});

test("shows a bounded emergency-access failure", () => {
  renderWithProviders(
    <ProductDenied canBreakGlass isPending={false} onBreakGlass={vi.fn()} showError />,
    "/store/products/missing",
  );

  expect(screen.getByRole("alert")).toHaveTextContent("Emergency access failed");
});
