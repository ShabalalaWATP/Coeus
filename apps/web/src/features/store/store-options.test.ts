import { csvToValues, productTypeLabel, visibleProductTags } from "./store-options";

test("formats known and unknown store option values", () => {
  expect(productTypeLabel("assessment_report")).toBe("Assessment report");
  expect(productTypeLabel("new_type")).toBe("new_type");
  expect(productTypeLabel("sigint_mock")).toBe("Signals intelligence data");
});

test("internal provenance tags stay searchable without dominating product cards", () => {
  expect(visibleProductTags(["collection", "MOCK", "mock-data", "sensor"])).toEqual([
    "collection",
    "sensor",
  ]);
});

test("normalises comma separated metadata values", () => {
  expect(csvToValues("ports, activity, , baltic ")).toEqual(["ports", "activity", "baltic"]);
});
