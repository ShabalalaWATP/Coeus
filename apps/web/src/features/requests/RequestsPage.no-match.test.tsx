import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { resetQueryClientForTests } from "../../app/query-client";
import type { Ticket } from "../../lib/api-client/tickets";
import { baseTicket, directory, renderRequests } from "../../test/requests-fixtures";

const noMatchTicket: Ticket = {
  ...baseTicket,
  state: "RFI_NO_MATCH",
  timeline: [
    ...baseTicket.timeline,
    {
      id: "timeline-no-match",
      eventType: "rfi_no_match",
      body: "No existing product matched this request.",
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

test("confirms no-match tasking as a new request from the workspace", async () => {
  const confirmedTicket: Ticket = {
    ...noMatchTicket,
    state: "JIOC_REVIEW",
    timeline: [
      ...noMatchTicket.timeline,
      {
        id: "timeline-confirmed",
        eventType: "tasking_confirmed",
        body: "Requester confirmed tasking as a new request.",
        actorUserId: "preview-user",
        createdAt: "2026-07-06T00:03:00Z",
      },
    ],
  };
  const fetchMock = vi.fn((url: string, init?: RequestInit) =>
    Promise.resolve(_responseFor(url, init, confirmedTicket)),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/ticket-1");

  expect(await screen.findByText("No existing product matches")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Request journey" }));
  expect(screen.getByText("Search existing intelligence").closest("li")).toHaveClass(
    "journey-step--current",
  );

  await userEvent.click(screen.getByRole("button", { name: "Yes, task as new request" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/tickets/ticket-1/no-match-consent",
      expect.objectContaining({
        body: JSON.stringify({ taskAsNewRequest: true }),
        method: "POST",
      }),
    ),
  );
  expect((await screen.findAllByText("JIOC REVIEW"))[0]).toBeVisible();
});

test("declines no-match tasking and cancels the request", async () => {
  const cancelledTicket: Ticket = {
    ...noMatchTicket,
    state: "CANCELLED",
    timeline: [
      ...noMatchTicket.timeline,
      {
        id: "timeline-declined",
        eventType: "tasking_declined",
        body: "customer declined tasking after no-match",
        actorUserId: "preview-user",
        createdAt: "2026-07-06T00:03:00Z",
      },
    ],
  };
  const fetchMock = vi.fn((url: string, init?: RequestInit) =>
    Promise.resolve(_responseFor(url, init, cancelledTicket)),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/ticket-1");

  await userEvent.click(await screen.findByRole("button", { name: "No, cancel request" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/tickets/ticket-1/no-match-consent",
      expect.objectContaining({
        body: JSON.stringify({ taskAsNewRequest: false }),
        method: "POST",
      }),
    ),
  );
  expect((await screen.findAllByText("CANCELLED"))[0]).toBeVisible();
});

test("shows no-match consent failures through the shared action error", async () => {
  const fetchMock = vi.fn((url: string) => {
    if (url.includes("/no-match-consent")) {
      return Promise.resolve({
        ok: false,
        status: 500,
        json: () =>
          Promise.resolve({ error: { code: "server_error", message: "Decision failed." } }),
      });
    }
    return Promise.resolve(_responseFor(url, undefined, noMatchTicket));
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/ticket-1");

  await userEvent.click(await screen.findByRole("button", { name: "Yes, task as new request" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Decision failed.");
});

function _responseFor(url: string, init: RequestInit | undefined, consentTicket: Ticket) {
  if (url.includes("/no-match-consent")) {
    return { ok: true, json: () => Promise.resolve(consentTicket) };
  }
  if (url.includes("/similar-requests")) {
    return { ok: true, json: () => Promise.resolve({ matches: [] }) };
  }
  if (url.includes("/users/directory")) {
    return { ok: true, json: () => Promise.resolve(directory) };
  }
  if (url.includes("/api/v1/tickets")) {
    return { ok: true, json: () => Promise.resolve({ tickets: [noMatchTicket] }) };
  }
  return { ok: true, json: () => Promise.resolve({ init }) };
}
