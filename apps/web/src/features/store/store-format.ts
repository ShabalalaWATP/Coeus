import type { StoreAsset } from "../../lib/api-client/store";

const DAY_MONTH = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});
const DAY_MONTH_YEAR = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

/** Render a coverage window the way an analyst would write it. */
export function formatCoverage(start: string | null, end: string | null): string | null {
  if (start === null) {
    return null;
  }
  if (end === null) {
    return `From ${formatDate(start, DAY_MONTH_YEAR)}`;
  }
  if (start === end) {
    return formatDate(start, DAY_MONTH_YEAR);
  }
  // Repeating the year on both ends reads as noise when they match.
  const sameYear = start.slice(0, 4) === end.slice(0, 4);
  const from = formatDate(start, sameYear ? DAY_MONTH : DAY_MONTH_YEAR);
  return `${from} to ${formatDate(end, DAY_MONTH_YEAR)}`;
}

const ASSET_LABELS: Record<string, string> = {
  csv: "Data",
  dataset: "Data",
  docx: "Document",
  geojson: "Map layer",
  image: "Imagery",
  pdf: "PDF",
  pptx: "Slides",
  xlsx: "Spreadsheet",
};

/** Summarise what a product actually contains, so the card answers it. */
export function assetSummary(assets: readonly StoreAsset[]): string | null {
  if (assets.length === 0) {
    return null;
  }
  const labels = [...new Set(assets.map((asset) => assetLabel(asset)))];
  return labels.join(" · ");
}

function assetLabel(asset: StoreAsset): string {
  if (asset.mimeType.startsWith("image/")) {
    return "Imagery";
  }
  return ASSET_LABELS[asset.assetType.toLowerCase()] ?? asset.assetType.toUpperCase();
}

/** Classification bands drive the marking colour, not the number itself. */
export function classificationTone(level: number): "low" | "medium" | "high" {
  if (level <= 1) {
    return "low";
  }
  return level <= 3 ? "medium" : "high";
}

function formatDate(iso: string, formatter: Intl.DateTimeFormat): string {
  const parsed = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? iso : formatter.format(parsed);
}
