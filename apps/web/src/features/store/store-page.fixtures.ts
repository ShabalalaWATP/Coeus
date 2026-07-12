import type { AuthSession } from "../../lib/api-client/auth";

export const visibleProduct = {
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
  tags: ["regional"],
  acgIds: ["acg-alpha"],
  status: "published",
  timePeriodStart: null,
  timePeriodEnd: null,
  geojsonRef: null,
  assets: [],
  matchScore: 1,
  matchReasons: ["visible"],
};

export const collectionProduct = {
  ...visibleProduct,
  id: "product-collection",
  title: "Collection Sensor Summary",
  productType: "unmapped_type",
  ownerTeam: "Collection",
  areaOrRegion: "North Sea",
  timePeriodStart: "2026-05-01",
};

export const readOnlyCollectionSession: AuthSession = {
  csrfToken: "test-csrf-token",
  user: {
    id: "collection-user",
    username: "collection@example.test",
    displayName: "Collection User",
    roles: ["Collection Manager"],
    defaultRoute: "/store",
    permissions: ["product:read", "product:search"],
  },
};

export const rfaManagerSession: AuthSession = {
  csrfToken: "test-csrf-token",
  user: {
    id: "rfa-user",
    username: "rfa.manager@example.test",
    displayName: "RFA Manager",
    roles: ["Request for Assessment Manager"],
    defaultRoute: "/rfa/queue",
    permissions: ["product:read", "product:search"],
  },
};
