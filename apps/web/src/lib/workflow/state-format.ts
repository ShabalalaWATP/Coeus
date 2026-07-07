export type StatusTone = "info" | "success" | "warning" | "critical";

export function formatWorkflowState(state: string) {
  return state.replaceAll("_", " ");
}

export function toneForState(state: string): StatusTone {
  if (state.includes("REJECT") || state.includes("DENIED")) {
    return "critical";
  }
  if (state.includes("REQUIRED") || state.includes("DRAFT")) {
    return "warning";
  }
  if (state.includes("READY") || state.includes("COMPLETE") || state.includes("DELIVERED")) {
    return "success";
  }
  return "info";
}
