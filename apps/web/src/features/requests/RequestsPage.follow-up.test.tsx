import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { resetQueryClientForTests } from "../../app/query-client";
import type { Ticket } from "../../lib/api-client/tickets";
import {
  baseTicket,
  directory,
  renderRequests,
  rfiSearchResults,
} from "../../test/requests-fixtures";

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("records reject-all feedback and refines the search", async () => {
  const offeredTicket: Ticket = { ...baseTicket, state: "RFI_MATCH_OFFERED" };
  const feedbackPromptTicket: Ticket = {
    ...offeredTicket,
    state: "NEW_TASKING_CONSENT",
    conversationStatus: "open",
    messages: [
      ...offeredTicket.messages,
      {
        id: "feedback-prompt",
        author: "assistant",
        body: "Thanks for reviewing those products. What was missing?",
        createdAt: "2026-07-06T00:03:00Z",
      },
    ],
    timeline: [
      ...offeredTicket.timeline,
      {
        id: "feedback-requested",
        eventType: "rfi_search_feedback_requested",
        body: "Istari asked what was missing.",
        actorUserId: "preview-user",
        createdAt: "2026-07-06T00:03:00Z",
      },
    ],
  };
  const feedbackRecordedTicket: Ticket = {
    ...feedbackPromptTicket,
    conversationStatus: "closed",
    timeline: [
      ...feedbackPromptTicket.timeline,
      {
        id: "feedback-recorded",
        eventType: "rfi_search_feedback_recorded",
        body: "Needs more recent coverage.",
        actorUserId: "preview-user",
        createdAt: "2026-07-06T00:04:00Z",
      },
    ],
  };
  const rejectedResults = {
    ...rfiSearchResults,
    ticketState: "NEW_TASKING_CONSENT",
    offers: [{ ...rfiSearchResults.offers[0], status: "rejected", rejectionReason: "Too old." }],
  };
  let currentTicket = offeredTicket;
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/offers/product-1/reject")) {
      currentTicket = feedbackPromptTicket;
      return response(rejectedResults);
    }
    if (url.endsWith("/rfi-search/ticket-1/feedback")) {
      currentTicket = feedbackRecordedTicket;
      return response(feedbackRecordedTicket);
    }
    if (url.endsWith("/rfi-search/ticket-1/refine")) return response(rfiSearchResults);
    if (url.includes("rfi-search") && url.endsWith("/results")) return response(rfiSearchResults);
    if (url.includes("/users/directory")) return response(directory);
    if (url.includes("/api/v1/tickets")) return response({ tickets: [currentTicket] });
    return response({ init });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderRequests("/app/requests/ticket-1");

  expect(await screen.findByText("Existing Baltic Port Assessment")).toBeVisible();
  await userEvent.type(screen.getByLabelText("Rejection reason"), "Too old.");
  await userEvent.click(screen.getByRole("button", { name: "Reject" }));
  await userEvent.type(
    await screen.findByLabelText("What was missing?"),
    "Needs more recent coverage.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));
  await userEvent.click(await screen.findByRole("button", { name: "Refine and search again" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/rfi-search/ticket-1/feedback",
      expect.objectContaining({
        body: JSON.stringify({ feedback: "Needs more recent coverage." }),
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/rfi-search/ticket-1/refine",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

function response(payload: unknown) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(payload) });
}
