import { csvToValues } from "./store-options";
import type { MetadataSuggestionInput, StoreProductCreateInput } from "../../lib/api-client/store";

export const initialProductUploadForm = {
  title: "Mock Harbour Activity Brief",
  summary: "MOCK DATA ONLY assessment of harbour activity.",
  description: "Synthetic product metadata for controlled store upload.",
  productType: "assessment_report",
  sourceType: "finished_assessment",
  ownerTeam: "RFA",
  areaOrRegion: "Baltic ports",
  classificationLevel: "2",
  status: "published" as "draft" | "published",
  tags: "ports, activity",
  assetName: "harbour-brief.pdf",
  assetType: "pdf",
  mimeType: "application/pdf",
  sizeBytes: "42000",
  sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  acgId: "",
};

export type ProductUploadFormState = typeof initialProductUploadForm;

export function productUploadMetadata(
  form: ProductUploadFormState,
): Omit<StoreProductCreateInput, "assets"> {
  return {
    title: form.title,
    summary: form.summary,
    description: form.description,
    productType: form.productType,
    sourceType: form.sourceType,
    ownerTeam: form.ownerTeam,
    areaOrRegion: form.areaOrRegion,
    classificationLevel: Number(form.classificationLevel),
    releasability: ["MOCK"],
    handlingCaveats: ["MOCK DATA ONLY"],
    tags: csvToValues(form.tags),
    acgIds: [form.acgId],
    status: form.status,
    geojsonRef: form.productType === "geographic_product" ? "mock://geojson/layer" : null,
  };
}

export function manualAssetMetadata(
  form: ProductUploadFormState,
): StoreProductCreateInput["assets"][number] {
  return {
    name: form.assetName,
    assetType: form.assetType,
    mimeType: form.mimeType,
    sizeBytes: Number(form.sizeBytes),
    sha256: form.sha256,
  };
}

export function metadataSuggestionInput(form: ProductUploadFormState): MetadataSuggestionInput {
  return {
    title: form.title,
    summary: form.summary,
    productType: form.productType,
    areaOrRegion: form.areaOrRegion,
  };
}
