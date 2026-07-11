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

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("tags and removes a collaborator as the request owner", async () => {
  const taggedTicket: Ticket = {
    ...baseTicket,
    collaborators: [
      {
        userId: "colleague-1",
        username: "colleague@example.test",
        displayName: "Customer Colleague",
        access: "editor",
        addedByUserId: "preview-user",
        createdAt: "2026-07-06T00:00:00Z",
      },
    ],
  };
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/collaborators/colleague-1")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(baseTicket) });
    }
    if (url.includes("/collaborators")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(taggedTicket) });
    }
    if (url.includes("/users/directory")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(directory) });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tickets: [baseTicket] }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}), init });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/ticket-1");

  await userEvent.type(await screen.findByLabelText("Search users"), "colleague");
  await screen.findByRole("option", { name: "Customer Colleague" });
  await userEvent.selectOptions(screen.getByLabelText("Tag a user"), "colleague@example.test");
  await userEvent.selectOptions(screen.getByLabelText("Access"), "editor");
  await userEvent.click(screen.getByRole("button", { name: "Tag user" }));

  expect(await screen.findByText("Customer Colleague")).toBeVisible();
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/tickets/ticket-1/collaborators",
    expect.objectContaining({
      body: JSON.stringify({ username: "colleague@example.test", access: "editor" }),
      method: "POST",
    }),
  );

  await userEvent.click(screen.getByRole("button", { name: "Remove Customer Colleague" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/tickets/ticket-1/collaborators/colleague-1",
      expect.objectContaining({ method: "DELETE" }),
    ),
  );
});

test("cancels an owned request with a recorded reason", async () => {
  const cancelledTicket: Ticket = {
    ...baseTicket,
    state: "CANCELLED",
    timeline: [
      ...baseTicket.timeline,
      {
        id: "timeline-cancelled",
        eventType: "ticket_cancelled",
        body: "No longer required.",
        actorUserId: "preview-user",
        createdAt: "2026-07-06T00:02:00Z",
      },
    ],
  };
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/cancel")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(cancelledTicket) });
    }
    if (url.includes("/users/directory")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(directory) });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tickets: [baseTicket] }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}), init });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/ticket-1");

  await userEvent.click((await screen.findAllByText("Cancel request"))[0]);
  await userEvent.type(screen.getByLabelText("Reason"), "No longer required.");
  await userEvent.click(screen.getByRole("button", { name: "Cancel request" }));

  expect((await screen.findAllByText("CANCELLED"))[0]).toBeVisible();
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/tickets/ticket-1/cancel",
    expect.objectContaining({
      body: JSON.stringify({ reason: "No longer required." }),
      method: "POST",
    }),
  );
});

test("shows request mutation failures instead of failing silently", async () => {
  const fetchMock = vi.fn((url: string) => {
    if (url.includes("/chat/messages")) {
      return Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
      });
    }
    if (url.includes("/users/directory")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(directory) });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tickets: [baseTicket] }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/ticket-1");

  await userEvent.type(await screen.findByLabelText("Message"), "Please use routine priority.");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));

  // The API error body carries the reason, so it is preferred over the
  // generic fallback message.
  expect(await screen.findByRole("alert")).toHaveTextContent("Failed.");
  await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("runs RFI search and accepts an offered product", async () => {
  const submittedTicket: Ticket = { ...baseTicket, state: "RFI_SEARCHING" };
  const unrelatedTicket: Ticket = {
    ...baseTicket,
    id: "ticket-2",
    reference: "RFI-0002",
    intake: { ...baseTicket.intake, title: "Unrelated request" },
  };
  const acceptedResults = {
    ...rfiSearchResults,
    ticketState: "CLOSED_EXISTING_PRODUCT_ACCEPTED",
    metrics: { ...rfiSearchResults.metrics, acceptedProductId: "product-1" },
    offers: [{ ...rfiSearchResults.offers[0], status: "accepted" }],
  };
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("rfi-search") && url.endsWith("/run")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(rfiSearchResults) });
    }
    if (url.includes("/offers/product-1/accept")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(acceptedResults) });
    }
    if (url.includes("/users/directory")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(directory) });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ tickets: [submittedTicket, unrelatedTicket] }),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}), init });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/ticket-1");

  await userEvent.click(await screen.findByRole("button", { name: "Run search" }));
  expect(await screen.findByText("Existing Baltic Port Assessment")).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Accept" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/rfi-search/ticket-1/offers/product-1/accept",
      expect.objectContaining({ method: "POST" }),
    ),
  );

  // Accepting an offer records the released product so the dashboard can link
  // to it without a refetch.
  await userEvent.click(screen.getByRole("link", { name: "Back to my requests" }));
  expect(await screen.findByRole("link", { name: /View released product/ })).toHaveAttribute(
    "href",
    "/store/products/product-1",
  );
  expect(screen.getByText("Unrelated request")).toBeVisible();
});

test("rejects an offered product with a reason", async () => {
  const offeredTicket: Ticket = { ...baseTicket, state: "RFI_MATCH_OFFERED" };
  const rejectedResults = {
    ...rfiSearchResults,
    ticketState: "ROUTE_ASSESSMENT",
    offers: [{ ...rfiSearchResults.offers[0], status: "rejected", rejectionReason: "Too old." }],
  };
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/offers/product-1/reject")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(rejectedResults) });
    }
    if (url.includes("rfi-search") && url.endsWith("/results")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(rfiSearchResults) });
    }
    if (url.includes("/users/directory")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(directory) });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ tickets: [offeredTicket] }),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}), init });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/ticket-1");

  expect(await screen.findByText("Existing Baltic Port Assessment")).toBeVisible();
  await userEvent.type(screen.getByLabelText("Rejection reason"), "Too old.");
  await userEvent.click(screen.getByRole("button", { name: "Reject" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/rfi-search/ticket-1/offers/product-1/reject",
      expect.objectContaining({
        body: JSON.stringify({ reason: "Too old." }),
        method: "POST",
      }),
    ),
  );
});

test("adds attachment metadata and timeline information from the workspace", async () => {
  const withAttachment: Ticket = {
    ...baseTicket,
    attachments: [
      {
        id: "attachment-1",
        name: "harbour.pdf",
        description: "Mock harbour imagery metadata.",
        sourceType: "metadata-only",
        createdAt: "2026-07-06T00:00:00Z",
      },
    ],
  };
  const withInformation: Ticket = {
    ...baseTicket,
    timeline: [
      ...baseTicket.timeline,
      {
        id: "timeline-2",
        eventType: "information_added",
        body: "Vessel schedule attached to the request.",
        actorUserId: "preview-user",
        createdAt: "2026-07-06T00:01:00Z",
      },
    ],
  };
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/attachments")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(withAttachment) });
    }
    if (url.includes("/timeline")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(withInformation) });
    }
    if (url.includes("/users/directory")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(directory) });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tickets: [baseTicket] }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}), init });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/ticket-1");

  await userEvent.click(await screen.findByText("Edit details manually"));
  await userEvent.type(screen.getByLabelText("Name"), "harbour.pdf");
  await userEvent.type(
    screen.getAllByLabelText("Description")[1],
    "Mock harbour imagery metadata.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Add metadata" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/tickets/ticket-1/attachments",
      expect.objectContaining({ method: "POST" }),
    ),
  );

  await userEvent.click(screen.getByText("Request history"));
  await userEvent.type(
    screen.getByLabelText("Additional information"),
    "Vessel schedule attached to the request.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Add information" }));

  expect(await screen.findByText("Vessel schedule attached to the request.")).toBeVisible();
});
