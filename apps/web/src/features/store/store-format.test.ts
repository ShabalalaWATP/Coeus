import { assetSummary, classificationTone, formatCoverage } from "./store-format";
import type { StoreAsset } from "../../lib/api-client/store";

function asset(overrides: Partial<StoreAsset>): StoreAsset {
  return {
    id: "asset-1",
    name: "brief.pdf",
    assetType: "pdf",
    mimeType: "application/pdf",
    sizeBytes: 1024,
    sha256: "a".repeat(64),
    previewKind: "pdf_metadata",
    ...overrides,
  };
}

test("writes a coverage window the way an analyst would", () => {
  expect(formatCoverage("2026-05-01", "2026-06-20")).toBe("1 May to 20 Jun 2026");
  expect(formatCoverage("2025-12-01", "2026-01-31")).toBe("1 Dec 2025 to 31 Jan 2026");
  expect(formatCoverage("2026-06-10", "2026-06-10")).toBe("10 Jun 2026");
  expect(formatCoverage("2026-05-01", null)).toBe("From 1 May 2026");
  expect(formatCoverage(null, "2026-06-20")).toBeNull();
  expect(formatCoverage(null, null)).toBeNull();
});

test("leaves an unparseable date alone rather than showing a broken one", () => {
  expect(formatCoverage("not-a-date", null)).toBe("From not-a-date");
});

test("summarises what a product actually contains", () => {
  expect(
    assetSummary([
      asset({}),
      asset({ id: "a2", assetType: "csv", mimeType: "text/csv" }),
      asset({ id: "a3", assetType: "image", mimeType: "image/png" }),
    ]),
  ).toBe("PDF · Data · Imagery");
  // Repeated formats are named once.
  expect(assetSummary([asset({}), asset({ id: "a2" })])).toBe("PDF");
  expect(assetSummary([])).toBeNull();
});

test("labels assets by what they are, falling back to the recorded type", () => {
  expect(assetSummary([asset({ assetType: "GeoJSON", mimeType: "application/geo+json" })])).toBe(
    "Map layer",
  );
  expect(assetSummary([asset({ assetType: "dataset", mimeType: "text/csv" })])).toBe("Data");
  expect(assetSummary([asset({ assetType: "image", mimeType: "image/jpeg" })])).toBe("Imagery");
  expect(assetSummary([asset({ assetType: "kml", mimeType: "application/vnd.kml" })])).toBe("KML");
});

test("bands classification levels for the marking colour", () => {
  expect(classificationTone(0)).toBe("low");
  expect(classificationTone(1)).toBe("low");
  expect(classificationTone(2)).toBe("medium");
  expect(classificationTone(3)).toBe("medium");
  expect(classificationTone(4)).toBe("high");
  expect(classificationTone(5)).toBe("high");
});
