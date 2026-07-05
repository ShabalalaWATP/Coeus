import { apiRequestJson } from "./client";

type StoreAsset = {
  id: string;
  name: string;
  assetType: string;
  mimeType: string;
  sizeBytes: number;
  sha256: string;
  previewKind: string;
};

export type StoreProduct = {
  id: string;
  reference: string;
  title: string;
  summary: string;
  description: string;
  productType: string;
  sourceType: string;
  ownerTeam: string;
  areaOrRegion: string;
  classificationLevel: number;
  releasability: string[];
  handlingCaveats: string[];
  tags: string[];
  acgIds: string[];
  projectId: string | null;
  status: string;
  timePeriodStart: string | null;
  timePeriodEnd: string | null;
  geojsonRef: string | null;
  assets: StoreAsset[];
};

type StoreSearchProduct = StoreProduct & {
  matchScore: number;
  matchReasons: string[];
};

export type StoreSearchFilters = {
  query?: string;
  productType?: string;
  region?: string;
  tag?: string;
  sourceType?: string;
  status?: string;
  projectId?: string;
};

export type StoreSearchResponse = {
  products: StoreSearchProduct[];
  total: number;
  facets: {
    productTypes: string[];
    regions: string[];
    tags: string[];
  };
};

export type StoreProductCreateInput = {
  title: string;
  summary: string;
  description: string;
  productType: string;
  sourceType: string;
  ownerTeam: string;
  areaOrRegion: string;
  classificationLevel: number;
  releasability: string[];
  handlingCaveats: string[];
  tags: string[];
  acgIds: string[];
  status: string;
  geojsonRef?: string | null;
  boundingBox?: { west: number; south: number; east: number; north: number } | null;
  assets: Array<{
    name: string;
    assetType: string;
    mimeType: string;
    sizeBytes: number;
    sha256: string;
  }>;
};

export type AssetAccessGrant = {
  assetId: string;
  downloadToken: string;
  expiresInSeconds: number;
};

export type MetadataSuggestionInput = {
  title: string;
  summary: string;
  productType: string;
  areaOrRegion: string;
};

export type MetadataSuggestion = {
  tags: string[];
  entities: string[];
  sourceType: string;
  acgIds: string[];
};

export async function searchStoreProducts(
  filters: StoreSearchFilters = {},
): Promise<StoreSearchResponse> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value.trim() !== "") {
      params.set(key, value);
    }
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return apiRequestJson<StoreSearchResponse>(`/api/v1/store/products${suffix}`, {
    method: "GET",
  });
}

export async function getStoreProduct(productId: string): Promise<StoreProduct> {
  return apiRequestJson<StoreProduct>(`/api/v1/store/products/${productId}`, { method: "GET" });
}

export async function getAssetAccess(
  productId: string,
  assetId: string,
): Promise<AssetAccessGrant> {
  return apiRequestJson<AssetAccessGrant>(
    `/api/v1/store/products/${productId}/assets/${assetId}/access`,
    { method: "GET" },
  );
}

export async function createStoreProduct(
  payload: StoreProductCreateInput,
  csrfToken: string,
): Promise<StoreProduct> {
  return apiRequestJson<StoreProduct>("/api/v1/store/products", {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function suggestStoreMetadata(
  payload: MetadataSuggestionInput,
  csrfToken: string,
): Promise<MetadataSuggestion> {
  return apiRequestJson<MetadataSuggestion>("/api/v1/store/metadata-suggestions", {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}
