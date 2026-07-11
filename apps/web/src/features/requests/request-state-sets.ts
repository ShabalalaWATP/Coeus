import type { TicketState } from "../../lib/api-client/tickets";

export const SIMILAR_NOTICE_STATES = new Set<TicketState>([
  "RFI_SEARCHING",
  "RFI_MATCH_OFFERED",
  "RFI_NO_MATCH",
  "JIOC_REVIEW",
  "COLLECT_CHOICE",
  "ANALYST_ASSIGNMENT",
  "ANALYST_IN_PROGRESS",
  "MANAGER_APPROVAL",
  "QC_REVIEW",
  "REWORK_REQUIRED",
]);
