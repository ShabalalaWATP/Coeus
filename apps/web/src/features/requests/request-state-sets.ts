import type { TicketState } from "../../lib/api-client/tickets";

export const SIMILAR_NOTICE_STATES = new Set<TicketState>(["ACTIVE_WORK_REVIEW"]);

export const INTAKE_STATES = new Set<TicketState>(["DRAFT_INTAKE", "INFO_REQUIRED"]);

export const PRODUCT_OFFER_STATES = new Set<TicketState>([
  "RFI_SEARCHING",
  "RFI_SEARCH_INCOMPLETE",
  "RFI_MATCH_OFFERED",
  "ACTIVE_WORK_REVIEW",
  "ACTIVE_WORK_SEARCH_INCOMPLETE",
  "RFI_NO_MATCH",
  "NEW_TASKING_CONSENT",
]);

// Legacy RFI_NO_MATCH is deliberately absent: the API only allows consent
// decisions from that state, so a cancel control would always 409.
export const CANCELABLE_STATES = new Set<TicketState>([
  "DRAFT_INTAKE",
  "INFO_REQUIRED",
  "RFI_SEARCHING",
  "RFI_SEARCH_INCOMPLETE",
  "RFI_MATCH_OFFERED",
  "NEW_TASKING_CONSENT",
  "JIOC_ROUTING_PENDING",
  "JIOC_INTERVENTION_HOLD",
  "ACTIVE_WORK_REVIEW",
  "ACTIVE_WORK_SEARCH_INCOMPLETE",
  "JIOC_REVIEW",
  "COLLECT_CHOICE",
  "ANALYST_ASSIGNMENT",
  "ANALYST_IN_PROGRESS",
  "MANAGER_APPROVAL",
  "QC_REVIEW",
  "REWORK_REQUIRED",
]);
