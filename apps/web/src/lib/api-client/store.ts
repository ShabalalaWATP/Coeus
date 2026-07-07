import { ApiError, apiRequestJson, pathSegment, resolveApiBaseUrl } from "./client";

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
  semanticLabels: string[];
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
  dateFrom?: string;
  dateTo?: string;
  ownerTeam?: string;
  page?: number;
  pageSize?: number;
};

export type StoreSearchResponse = {
  products: StoreSearchProduct[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
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
  semanticLabels?: string[];
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
  semanticLabels: string[];
};

export async function searchStoreProducts(
  filters: StoreSearchFilters = {},
): Promise<StoreSearchResponse> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    const normalised = value === undefined ? "" : String(value).trim();
    if (normalised !== "") {
      params.set(key, normalised);
    }
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return apiRequestJson<StoreSearchResponse>(`/api/v1/store/products${suffix}`, {
    method: "GET",
  });
}

export async function getStoreProduct(productId: string): Promise<StoreProduct> {
  return apiRequestJson<StoreProduct>(`/api/v1/store/products/${pathSegment(productId)}`, {
    method: "GET",
  });
}

export async function breakGlassStoreProduct(
  productId: string,
  reason: string,
  csrfToken: string,
): Promise<StoreProduct> {
  return apiRequestJson<StoreProduct>(
    `/api/v1/store/products/${pathSegment(productId)}/break-glass`,
    {
      body: JSON.stringify({ reason }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}

export async function getAssetAccess(
  productId: string,
  assetId: string,
): Promise<AssetAccessGrant> {
  return apiRequestJson<AssetAccessGrant>(
    `/api/v1/store/products/${pathSegment(productId)}/assets/${pathSegment(assetId)}/access`,
    { method: "GET" },
  );
}

export async function breakGlassAssetAccess(
  productId: string,
  assetId: string,
  reason: string,
  csrfToken: string,
): Promise<AssetAccessGrant> {
  return apiRequestJson<AssetAccessGrant>(
    `/api/v1/store/products/${pathSegment(productId)}/assets/${pathSegment(
      assetId,
    )}/break-glass-access`,
    {
      body: JSON.stringify({ reason }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    },
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

export async function uploadStoreProduct(
  payload: Omit<StoreProductCreateInput, "assets">,
  file: File,
  csrfToken: string,
): Promise<StoreProduct> {
  const form = new FormData();
  form.append("metadata", JSON.stringify(payload));
  form.append("asset", file);
  return apiRequestJson<StoreProduct>("/api/v1/store/products/upload", {
    body: form,
    headers: { "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function downloadAssetBlob(
  productId: string,
  assetId: string,
  token: string,
): Promise<Blob> {
  const response = await fetch(
    `${resolveApiBaseUrl()}/api/v1/store/products/${pathSegment(productId)}/assets/${pathSegment(
      assetId,
    )}/download`,
    {
      // The response varies with the token header, so bypass the HTTP cache.
      cache: "no-store",
      credentials: "include",
      headers: { "X-Asset-Token": token },
      method: "GET",
    },
  );
  if (!response.ok) {
    throw new ApiError(
      response.status,
      "asset_download_failed",
      `Asset download failed with status ${response.status}`,
    );
  }
  return response.blob();
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
