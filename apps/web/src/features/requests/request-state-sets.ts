import type { RfiProductOffer } from "../../lib/api-client/rfi-search";
import type { Ticket, TicketState } from "../../lib/api-client/tickets";

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
  // Accepting an offer closes the request. The panel stays so the requester can
  // still see which product answered it and that nothing was tasked; every
  // control inside it is already gated on the open states.
  "CLOSED_EXISTING_PRODUCT_ACCEPTED",
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

export function rfiFollowUpState(ticket?: Ticket, offers: RfiProductOffer[] = []) {
  let requested = -1;
  let recorded = -1;
  let refined = -1;
  ticket?.timeline.forEach((entry, index) => {
    if (entry.eventType === "rfi_search_feedback_requested") requested = index;
    if (entry.eventType === "rfi_search_feedback_recorded") recorded = index;
    if (entry.eventType === "rfi_refined_search_started") refined = index;
  });
  const followUpState = ["NEW_TASKING_CONSENT", "RFI_SEARCH_INCOMPLETE"].includes(
    ticket?.state ?? "",
  );
  return {
    feedbackState: {
      complete: requested >= 0 && recorded > requested,
      pending: requested > recorded,
    },
    refineAvailable: requested >= 0 && recorded > Math.max(requested, refined),
    rejectedOfferFollowUp:
      followUpState && (requested >= 0 || offers.some((offer) => offer.status === "rejected")),
  };
}
