import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { resetQueryClientForTests } from "../../app/query-client";
import type { Ticket } from "../../lib/api-client/tickets";
import { baseTicket, directory, renderRequests } from "../../test/requests-fixtures";

const collectChoiceTicket: Ticket = {
  ...baseTicket,
  state: "COLLECT_CHOICE",
  timeline: [
    ...baseTicket.timeline,
    {
      id: "timeline-collect-choice",
      eventType: "collect_choice_requested",
      body: "Customer asked to choose raw collect or collect plus analysis.",
      actorUserId: "preview-user",
      createdAt: "2026-07-06T00:02:00Z",
    },
  ],
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("submits a raw-only collect choice from the workspace panel", async () => {
  const chosenTicket: Ticket = {
    ...collectChoiceTicket,
    state: "ANALYST_ASSIGNMENT",
    collectDisposition: "raw",
  };
  const fetchMock = vi.fn((url: string, init?: RequestInit) =>
    Promise.resolve(_responseFor(url, init, chosenTicket)),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/ticket-1");

  expect(await screen.findByText("Collection has been approved")).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Raw collect only" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/tickets/ticket-1/collect-choice",
      expect.objectContaining({
        body: JSON.stringify({ analysed: false }),
        method: "POST",
      }),
    ),
  );
});

test("submits an analysed collect choice from the workspace panel", async () => {
  const chosenTicket: Ticket = {
    ...collectChoiceTicket,
    state: "ANALYST_ASSIGNMENT",
    collectDisposition: "analysed",
  };
  const fetchMock = vi.fn((url: string, init?: RequestInit) =>
    Promise.resolve(_responseFor(url, init, chosenTicket)),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/ticket-1");

  await userEvent.click(await screen.findByRole("button", { name: "Collect plus RFA analysis" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/tickets/ticket-1/collect-choice",
      expect.objectContaining({
        body: JSON.stringify({ analysed: true }),
        method: "POST",
      }),
    ),
  );
});

function _responseFor(url: string, init: RequestInit | undefined, chosenTicket: Ticket) {
  if (url.includes("/collect-choice")) {
    return { ok: true, json: () => Promise.resolve(chosenTicket) };
  }
  if (url.includes("/similar-requests")) {
    return { ok: true, json: () => Promise.resolve({ matches: [] }) };
  }
  if (url.includes("/users/directory")) {
    return { ok: true, json: () => Promise.resolve(directory) };
  }
  if (url.includes("/api/v1/tickets")) {
    return { ok: true, json: () => Promise.resolve({ tickets: [collectChoiceTicket] }) };
  }
  return { ok: true, json: () => Promise.resolve({ init }) };
}
