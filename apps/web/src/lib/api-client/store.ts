import { apiRequest, apiRequestJson, pathSegment } from "./client";
import type { components } from "./generated/openapi";

export type StoreAsset = components["schemas"]["StoreAssetResponse"];
export type StoreProduct = components["schemas"]["StoreProductResponse"];

export type StoreSearchFilters = {
  query?: string;
  productType?: string;
  region?: string;
  tag?: string;
  sourceType?: string;
  status?: string;
  dateFrom?: string;
  dateTo?: string;
  ownerTeam?: string;
  page?: number;
  pageSize?: number;
};

export type StoreSearchResponse = components["schemas"]["StoreSearchResponse"];
export type StoreProductCreateInput = components["schemas"]["StoreProductCreateRequest"];
export type AssetAccessGrant = components["schemas"]["AssetAccessResponse"];

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
  const response = await apiRequest(
    `/api/v1/store/products/${pathSegment(productId)}/assets/${pathSegment(assetId)}/download`,
    {
      // The response varies with the token header, so bypass the HTTP cache.
      cache: "no-store",
      headers: { "X-Asset-Token": token },
      method: "GET",
    },
  );
  return response.blob();
}

export async function previewStoreAssetBlob(
  productId: string,
  assetId: string,
  token: string,
): Promise<Blob> {
  const response = await apiRequest(
    `/api/v1/store/products/${pathSegment(productId)}/assets/${pathSegment(assetId)}/preview`,
    {
      cache: "no-store",
      headers: { "X-Asset-Token": token },
      method: "GET",
    },
  );
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
