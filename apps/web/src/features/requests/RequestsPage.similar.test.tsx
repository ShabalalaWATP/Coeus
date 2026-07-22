import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { resetQueryClientForTests } from "../../app/query-client";
import type { Ticket } from "../../lib/api-client/tickets";
import { baseTicket, directory, renderRequests } from "../../test/requests-fixtures";
import { SimilarRequestNoticePanel } from "./SimilarRequestNoticePanel";

const submittedTicket: Ticket = {
  ...baseTicket,
  state: "ACTIVE_WORK_REVIEW",
  intake: { ...baseTicket.intake, missingInformation: [] },
  isReadyForSubmission: true,
};

const cancelledTicket: Ticket = {
  ...submittedTicket,
  state: "CANCELLED",
};

const similarNotice = {
  matches: [
    {
      ticketId: "related-1",
      reference: "TCK-0002",
      title: "Vessel movements Gulf of Finland",
      state: "RFI_SEARCHING",
      score: 0.72,
      reasons: ["similarity:vector:0.83", "similarity:metadata-region"],
      alreadyLinked: false,
    },
  ],
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("shows a customer similar-request notice and lets the requester continue", async () => {
  vi.stubGlobal("fetch", similarFetch());

  renderRequests("/app/requests/ticket-1");

  expect(await screen.findByText("Similar request in progress")).toBeVisible();
  expect(screen.getByText("TCK-0002")).toBeVisible();
  expect(screen.getByText("Vessel movements Gulf of Finland")).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "None answer my need" }));

  await waitFor(() =>
    expect(screen.queryByText("Similar request in progress")).not.toBeInTheDocument(),
  );
});

test("surfaces customer join failures through the workspace action error", async () => {
  vi.stubGlobal("fetch", similarFetch({ joinFails: true }));

  renderRequests("/app/requests/ticket-1");

  await userEvent.click(await screen.findByRole("button", { name: "Join this work" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Join failed.");
});

test("posts a successful customer join request with CSRF protection", async () => {
  const fetchMock = similarFetch();
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/ticket-1");

  await userEvent.click(await screen.findByRole("button", { name: "Join this work" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/similar-requests/tickets/ticket-1/join/related-1",
      expect.objectContaining({
        headers: { "X-CSRF-Token": "test-csrf-token" },
        method: "POST",
      }),
    ),
  );
});

test("does not show the notice for a ticket outside the eligible states", async () => {
  vi.stubGlobal("fetch", similarFetch({ ticket: cancelledTicket }));

  renderRequests("/app/requests/ticket-1");

  expect(await screen.findByText("TCK-0001")).toBeVisible();
  expect(screen.queryByText("Similar request in progress")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Join this work" })).not.toBeInTheDocument();
});

test("shows loading and retry states, then hides an empty active-work result", async () => {
  const onRetry = vi.fn();
  const props = {
    isJoining: false,
    isQueryError: false,
    notice: undefined,
    onContinue: vi.fn(),
    onJoin: vi.fn(),
    onRetry,
  };
  const view = render(<SimilarRequestNoticePanel {...props} isLoading />);
  expect(screen.getByText("Checking for similar open requests")).toBeVisible();

  view.rerender(<SimilarRequestNoticePanel {...props} isLoading={false} isQueryError />);
  await userEvent.click(screen.getByRole("button", { name: "Retry check" }));
  expect(onRetry).toHaveBeenCalledTimes(1);

  view.rerender(
    <SimilarRequestNoticePanel {...props} isLoading={false} notice={{ matches: [] }} />,
  );
  expect(screen.queryByLabelText("Similar request check")).not.toBeInTheDocument();
});

function similarFetch(options: { joinFails?: boolean; ticket?: Ticket } = {}) {
  const ticket = options.ticket ?? submittedTicket;
  return vi.fn((url: string) => {
    if (url.endsWith("/similar-requests/tickets/ticket-1/continue")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ...submittedTicket, state: "NEW_TASKING_CONSENT" }),
      });
    }
    if (url.includes("/similar-requests/tickets/ticket-1/join/related-1")) {
      return Promise.resolve(
        options.joinFails
          ? {
              ok: false,
              status: 500,
              json: () =>
                Promise.resolve({ error: { code: "join_failed", message: "Join failed." } }),
            }
          : {
              ok: true,
              json: () => Promise.resolve({ joinedTicketId: "related-1", reference: "TCK-0002" }),
            },
      );
    }
    if (url.includes("/similar-requests/tickets/ticket-1")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(similarNotice) });
    }
    if (url.includes("/users/directory")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(directory) });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ tickets: [ticket] }),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
}
