import { csvToValues, productTypeLabel } from "./store-options";

test("formats known and unknown store option values", () => {
  expect(productTypeLabel("assessment_report")).toBe("Assessment report");
  expect(productTypeLabel("new_type")).toBe("new_type");
});

test("normalises comma separated metadata values", () => {
  expect(csvToValues("ports, activity, , baltic ")).toEqual(["ports", "activity", "baltic"]);
});
