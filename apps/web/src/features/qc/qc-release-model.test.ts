import { csvToValues, initialReleaseForm, selectedAcgId } from "./qc-release-model";
import type { AccessControlGroup } from "../../lib/api-client/client";

const acg: AccessControlGroup = {
  id: "first-acg",
  code: "ACG-ALPHA-REGIONAL",
  name: "Alpha Regional",
  description: "Mock access group.",
  ownerUserId: "admin-1",
  isActive: true,
  memberUserIds: ["user-1"],
};

test("normalises QC release metadata helpers", () => {
  expect(csvToValues("MOCK,  REL")).toEqual(["MOCK", "REL"]);
  expect(selectedAcgId({ ...initialReleaseForm, acgId: "selected-acg" }, [])).toBe("selected-acg");
  expect(selectedAcgId(initialReleaseForm, [acg])).toBe("first-acg");
  expect(selectedAcgId(initialReleaseForm, [])).toBe("");
});
