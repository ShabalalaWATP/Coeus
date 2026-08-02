export const productTypeOptions = [
  ["assessment_report", "Assessment report"],
  ["intelligence_summary", "Intelligence summary"],
  ["satellite_imagery_product", "Satellite imagery product"],
  ["sigint_mock", "Signals intelligence data"],
  ["geographic_product", "Geographic product"],
  ["database_extract", "Database extract"],
  ["product_bundle", "Product bundle"],
  ["finished_output", "Finished Istari output"],
] as const;

export function productTypeLabel(value: string) {
  return productTypeOptions.find(([option]) => option === value)?.[1] ?? value;
}

const provenanceTags = new Set(["mock", "mock-data", "synthetic-conflict", "synthetic-exercise"]);

export function visibleProductTags(tags: string[]) {
  return tags.filter((tag) => !provenanceTags.has(tag.toLowerCase()));
}

export function csvToValues(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}
