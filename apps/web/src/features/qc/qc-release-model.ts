export const initialReleaseForm = {
  classificationLevel: "2",
  releasability: "MOCK",
  caveats: "MOCK DATA ONLY",
  acgId: "",
  reason: "",
  rejectionReason: "",
};

export type QcReleaseFormState = typeof initialReleaseForm;

export function csvToValues(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function selectedAcgId(form: QcReleaseFormState) {
  return form.acgId;
}
