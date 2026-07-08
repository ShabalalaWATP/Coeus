import type { TicketState } from "../../lib/api-client/tickets";

export const SIMILAR_NOTICE_STATES = new Set<TicketState>([
  "RFI_SEARCHING",
  "RFI_MATCH_OFFERED",
  "RFI_NO_MATCH",
  "ROUTE_ASSESSMENT",
  "RFA_MANAGER_REVIEW",
  "CM_MANAGER_REVIEW",
  "ANALYST_ASSIGNMENT",
  "ANALYST_IN_PROGRESS",
  "QC_REVIEW",
  "REWORK_REQUIRED",
  "MANAGER_RELEASE",
]);
