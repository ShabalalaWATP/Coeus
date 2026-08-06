import type { TicketSummary } from "../../lib/api-client/tickets";

const CLOSED_TICKET_STATES = new Set<TicketSummary["state"]>([
  "CLOSED_DELIVERED",
  "CLOSED_REQUIREMENT_MET",
  "CLOSED_REANALYSIS_DECLINED",
  "CLOSED_EXISTING_PRODUCT_ACCEPTED",
  "CLOSED_UNANSWERED",
  "CLOSED_JOINED_EXISTING_WORK",
  "CANCELLED",
]);

export function ticketMetrics(
  tickets: Array<Pick<TicketSummary, "state"> & Partial<Pick<TicketSummary, "customerStatus">>>,
) {
  const draftStates = new Set(["DRAFT_INTAKE", "INFO_REQUIRED"]);
  const awaitingActionStates = new Set([
    "RFI_MATCH_OFFERED",
    "RFI_SEARCH_INCOMPLETE",
    "ACTIVE_WORK_REVIEW",
    "ACTIVE_WORK_SEARCH_INCOMPLETE",
    "NEW_TASKING_CONSENT",
    "COLLECT_CHOICE",
    "DISSEMINATION_READY",
  ]);
  return {
    total: tickets.length,
    draft: tickets.filter((ticket) => draftStates.has(ticket.state)).length,
    awaitingAction: tickets.filter(
      (ticket) => ticket.customerStatus?.actionRequired ?? awaitingActionStates.has(ticket.state),
    ).length,
    inProgress: tickets.filter(
      (ticket) =>
        !draftStates.has(ticket.state) &&
        !awaitingActionStates.has(ticket.state) &&
        !isClosedTicket(ticket.state),
    ).length,
    completed: tickets.filter((ticket) => isClosedTicket(ticket.state)).length,
  };
}

export function isClosedTicket(state: TicketSummary["state"]) {
  return CLOSED_TICKET_STATES.has(state);
}

export type RequestGroupKey = "action" | "draft" | "progress";

export type RequestGroup<T> = {
  key: RequestGroupKey;
  title: string;
  hint: string;
  tickets: T[];
};

const GROUP_COPY: Record<RequestGroupKey, { title: string; hint: string }> = {
  action: {
    title: "Needs your action",
    hint: "Waiting on a decision or answer from you before they can move on.",
  },
  draft: {
    title: "Drafts",
    hint: "Started but not submitted yet, so nobody is working on them.",
  },
  progress: {
    title: "With Istari",
    hint: "Submitted and being worked. Nothing is needed from you.",
  },
};

type GroupableTicket = Pick<TicketSummary, "state" | "updatedAt" | "reference"> &
  Partial<Pick<TicketSummary, "customerStatus">>;

// Priority is free intake text rather than a scale, so there is nothing
// dependable to order it by. These three all sort on values the system sets.
export const REQUEST_SORTS = [
  { value: "recent", label: "Recently updated" },
  { value: "oldest", label: "Longest without an update" },
  { value: "reference", label: "Reference" },
] as const;

export type RequestSort = (typeof REQUEST_SORTS)[number]["value"];

/**
 * Split open requests into the three things a requester can do about them:
 * act on it, finish writing it, or wait. Ordered so anything blocked on the
 * requester is read first, and empty groups are dropped rather than shown bare.
 */
export function groupOpenRequests<T extends GroupableTicket>(
  tickets: T[],
  sort: RequestSort = "recent",
): RequestGroup<T>[] {
  const buckets: Record<RequestGroupKey, T[]> = { action: [], draft: [], progress: [] };
  for (const ticket of tickets) {
    buckets[requestGroupKey(ticket)].push(ticket);
  }
  const order: RequestGroupKey[] = ["action", "draft", "progress"];
  return order
    .filter((key) => buckets[key].length > 0)
    .map((key) => ({ key, ...GROUP_COPY[key], tickets: sortRequests(buckets[key], sort) }));
}

export function requestGroupKey(ticket: GroupableTicket): RequestGroupKey {
  // The API decides whether the viewer owes an answer, so a collaborator does
  // not see someone else's decision as their own outstanding action.
  if (ticket.customerStatus?.actionRequired ?? isAwaitingCustomerAction(ticket.state)) {
    return "action";
  }
  return ticket.state === "DRAFT_INTAKE" || ticket.state === "INFO_REQUIRED" ? "draft" : "progress";
}

export function sortRequests<T extends GroupableTicket>(tickets: T[], sort: RequestSort): T[] {
  const compare: Record<RequestSort, (left: T, right: T) => number> = {
    recent: (left, right) => right.updatedAt.localeCompare(left.updatedAt),
    oldest: (left, right) => left.updatedAt.localeCompare(right.updatedAt),
    reference: (left, right) => left.reference.localeCompare(right.reference),
  };
  return [...tickets].sort(compare[sort]);
}

// Mirrors ACTION_STATES in the API's customer_status service. Used only when a
// summary arrives without customerStatus; INFO_REQUIRED belongs here because the
// request is blocked until the requester supplies more detail.
const AWAITING_CUSTOMER_STATES = new Set<TicketSummary["state"]>([
  "INFO_REQUIRED",
  "RFI_MATCH_OFFERED",
  "RFI_NO_MATCH",
  "RFI_SEARCH_INCOMPLETE",
  "ACTIVE_WORK_REVIEW",
  "ACTIVE_WORK_SEARCH_INCOMPLETE",
  "NEW_TASKING_CONSENT",
  "COLLECT_CHOICE",
  "DISSEMINATION_READY",
]);

export function isAwaitingCustomerAction(state: TicketSummary["state"]) {
  return AWAITING_CUSTOMER_STATES.has(state);
}
