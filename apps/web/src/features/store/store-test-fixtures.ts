import { vi } from "vitest";

export const productFixture = {
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
  semanticLabels: ["assessment", "maritime"],
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

export function stubObjectUrls() {
  const createObjectURL = vi.fn(() => "blob:mock-asset");
  const revokeObjectURL = vi.fn();
  Object.assign(URL, { createObjectURL, revokeObjectURL });
  return { createObjectURL, revokeObjectURL };
}
