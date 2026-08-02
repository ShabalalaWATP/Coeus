export type StatusTone = "info" | "success" | "warning" | "critical";

export function formatWorkflowState(state: string) {
  const outcomeLabels: Record<string, string> = {
    CLOSED_EXISTING_PRODUCT_ACCEPTED: "Successfully fulfilled",
    CLOSED_UNANSWERED: "Closed unfulfilled",
  };
  if (outcomeLabels[state]) return outcomeLabels[state];
  const acronyms = new Set(["RFI", "JIOC", "QC", "RFA"]);
  return state
    .split("_")
    .map((word, index) =>
      acronyms.has(word) ? word : index === 0 ? titleCase(word) : word.toLowerCase(),
    )
    .join(" ");
}

function titleCase(value: string) {
  const lower = value.toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

export function toneForState(state: string): StatusTone {
  if (state.includes("REJECT") || state.includes("DENIED")) {
    return "critical";
  }
  if (
    state.includes("REQUIRED") ||
    state.includes("DRAFT") ||
    state.includes("INCOMPLETE") ||
    state.includes("UNANSWERED")
  ) {
    return "warning";
  }
  if (state.includes("READY") || state.includes("COMPLETE") || state.includes("DELIVERED")) {
    return "success";
  }
  return "info";
}
