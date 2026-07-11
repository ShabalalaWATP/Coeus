import { csvToValues, initialReleaseForm, selectedAcgId } from "./qc-release-model";

test("normalises QC release metadata helpers", () => {
  expect(csvToValues("MOCK,  REL")).toEqual(["MOCK", "REL"]);
  expect(selectedAcgId({ ...initialReleaseForm, acgId: "selected-acg" })).toBe("selected-acg");
  expect(selectedAcgId(initialReleaseForm)).toBe("");
});
