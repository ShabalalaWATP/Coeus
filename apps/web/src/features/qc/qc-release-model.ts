import type { AccessControlGroup } from "../../lib/api-client/client";

export const initialReleaseForm = {
  classificationLevel: "2",
  releasability: "MOCK",
  caveats: "MOCK DATA ONLY",
  acgId: "",
  reason: "QC checklist complete.",
  rejectionReason: "",
};

export type QcReleaseFormState = typeof initialReleaseForm;

export function csvToValues(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function selectedAcgId(form: QcReleaseFormState, acgs: AccessControlGroup[] = []) {
  return form.acgId || acgs[0]?.id || "";
}
