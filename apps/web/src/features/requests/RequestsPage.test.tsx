import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RequestsPage from "./RequestsPage";
import { resetQueryClientForTests } from "../../app/query-client";
import type { Ticket } from "../../lib/api-client/tickets";
import { baseTicket, directory, fetchByUrl, renderRequests } from "../../test/requests-fixtures";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders a tickets error state with retry", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );

  renderWithProviders(<RequestsPage />);

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
});

test("shows the dashboard and opens the new request workspace", async () => {
  vi.stubGlobal(
    "fetch",
    fetchByUrl([
      ["/api/v1/tickets", { tickets: [baseTicket] }],
      ["/feedback/requests", { requests: [] }],
    ]),
  );

  renderRequests("/app/requests");

  expect(await screen.findByRole("heading", { name: "My Requests" })).toBeVisible();
  expect(await screen.findByRole("button", { name: /TCK-0001/ })).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Open new request" }));

  expect(await screen.findByRole("heading", { name: "Request" })).toBeVisible();
  expect(screen.getByLabelText("Message")).toBeVisible();
  expect(screen.getByText(/Hi, I am Istari/)).toBeVisible();
});

test("loads older compact request summaries through the server cursor", async () => {
  const older = { ...baseTicket, id: "ticket-older", reference: "TCK-0000" };
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    void init;
    if (url.includes("cursor=ticket-1")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ tickets: [older], nextCursor: null }),
      });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ tickets: [baseTicket], nextCursor: "ticket-1" }),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ requests: [] }) });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests");
  await userEvent.click(await screen.findByRole("button", { name: "Load older requests" }));

  expect(await screen.findByRole("button", { name: /TCK-0000/ })).toBeVisible();
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("cursor=ticket-1"),
    expect.objectContaining({ method: "GET" }),
  );
});

test("shows a missing state for an unknown direct request URL", async () => {
  vi.stubGlobal(
    "fetch",
    fetchByUrl([
      ["/api/v1/tickets", { tickets: [baseTicket] }],
      ["/feedback/requests", { requests: [] }],
    ]),
  );

  renderRequests("/app/requests/missing-ticket");

  expect(await screen.findByText("Request not found")).toBeVisible();
  expect(
    screen.getByText("This request is not visible to your account or no longer exists."),
  ).toBeVisible();
  expect(screen.queryByLabelText("Message")).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Back to my requests" }));

  expect(await screen.findByRole("heading", { name: "My Requests" })).toBeVisible();
});

test("locks an existing-request route until its exact ticket has loaded", async () => {
  let resolveDetail: ((response: Response) => void) | undefined;
  const detail = new Promise<Response>((resolve) => {
    resolveDetail = resolve;
  });
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    void init;
    if (url.endsWith("/api/v1/tickets/ticket-1")) {
      return detail;
    }
    if (url.endsWith("/api/v1/tickets")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ tickets: [baseTicket], nextCursor: null }),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/ticket-1");

  expect(await screen.findByRole("status")).toHaveTextContent("Loading request");
  expect(screen.queryByLabelText("Message")).not.toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);

  resolveDetail?.({ ok: true, json: () => Promise.resolve(baseTicket) } as Response);
  expect(await screen.findByText("Edit details manually")).toBeVisible();
});

test("creates a ticket from chat and shows the captured details checklist", async () => {
  const createdTicket = { ...baseTicket, messages: baseTicket.messages.slice(0, 2) };
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/chat/messages")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(createdTicket) });
    }
    if (url.includes("/users/directory")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(directory) });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tickets: [] }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}), status: 200, init });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests/new");

  await userEvent.type(screen.getByLabelText("Message"), "Need a Baltic ports brief.");
  await userEvent.click(screen.getByRole("button", { name: "Send" }));

  expect(await screen.findByText("TCK-0001")).toBeVisible();
  expect(screen.getByText("Request details")).toBeVisible();
  expect(screen.getByText("5 of 10 captured from the conversation.")).toBeVisible();
  expect(screen.getByText("Baltic Ports Brief")).toBeVisible();
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/chat/messages",
    expect.objectContaining({
      body: JSON.stringify({ message: "Need a Baltic ports brief." }),
      method: "POST",
    }),
  );
});

test("edits intake manually and submits once complete", async () => {
  const readyTicket: Ticket = {
    ...baseTicket,
    intake: {
      ...baseTicket.intake,
      priority: "routine",
      customerSuccessCriteria: "Clear summary.",
      missingInformation: [],
      confidence: 1,
    },
    isReadyForSubmission: true,
  };
  const submittedTicket: Ticket = { ...readyTicket, state: "RFI_SEARCHING" };
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/intake")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(readyTicket) });
    }
    if (url.includes("/submit")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(submittedTicket) });
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
  await userEvent.type(screen.getByLabelText("Priority"), "routine");
  await userEvent.type(screen.getByLabelText("Success criteria"), "Clear summary.");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  const submit = await screen.findByRole("button", { name: "Submit" });
  await waitFor(() => expect(submit).toBeEnabled());
  await userEvent.click(submit);

  expect((await screen.findAllByText("RFI searching")).length).toBeGreaterThan(0);

  // Submission opens the transient journey popup so the requester sees what happens next.
  expect(await screen.findByRole("dialog", { name: "Request journey" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Close journey" }));
  expect(screen.queryByRole("dialog", { name: "Request journey" })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Request journey" }));
  expect(await screen.findByText("You are here")).toBeVisible();
});

test("hides the mock-data badge from users who can create requests", async () => {
  vi.stubGlobal(
    "fetch",
    fetchByUrl([
      ["/api/v1/tickets", { tickets: [baseTicket] }],
      ["/feedback/requests", { requests: [] }],
    ]),
  );

  renderRequests("/app/requests/new");

  expect(await screen.findByRole("heading", { name: "Request" })).toBeVisible();
  expect(screen.queryByText("MOCK DATA ONLY")).not.toBeInTheDocument();
});

test("confirms delivery of a disseminated request from the dashboard", async () => {
  const readyTicket: Ticket = { ...baseTicket, state: "DISSEMINATION_READY" };
  const closedTicket: Ticket = { ...readyTicket, state: "CLOSED_DELIVERED" };
  const fetchMock = vi.fn((url: string) => {
    if (url.includes("/confirm-delivery")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(closedTicket) });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tickets: [readyTicket] }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests");

  await userEvent.click(await screen.findByRole("button", { name: "Confirm receipt and close" }));

  expect(await screen.findByText("Closed delivered")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Confirm receipt and close" }),
  ).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/tickets/ticket-1/confirm-delivery",
    expect.objectContaining({
      headers: { "X-CSRF-Token": "test-csrf-token" },
      method: "POST",
    }),
  );
});

test("shows a dismissible error when delivery confirmation fails", async () => {
  const readyTicket: Ticket = { ...baseTicket, state: "DISSEMINATION_READY" };
  const fetchMock = vi.fn((url: string) => {
    if (url.includes("/confirm-delivery")) {
      return Promise.resolve({
        ok: false,
        status: 409,
        json: () =>
          Promise.resolve({ error: { code: "invalid_state", message: "Not ready to close." } }),
      });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tickets: [readyTicket] }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests");

  await userEvent.click(await screen.findByRole("button", { name: "Confirm receipt and close" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Not ready to close.");
  await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("clears a delivery confirmation error after a successful retry", async () => {
  const readyTicket: Ticket = { ...baseTicket, state: "DISSEMINATION_READY" };
  const closedTicket: Ticket = { ...readyTicket, state: "CLOSED_DELIVERED" };
  const fetchMock = vi.fn((url: string) => {
    if (url.includes("/confirm-delivery")) {
      const confirmationCalls = fetchMock.mock.calls.filter(([calledUrl]) =>
        String(calledUrl).includes("/confirm-delivery"),
      );
      if (confirmationCalls.length === 1) {
        return Promise.resolve({
          ok: false,
          status: 409,
          json: () =>
            Promise.resolve({ error: { code: "invalid_state", message: "Not ready to close." } }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(closedTicket) });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tickets: [readyTicket] }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests");

  const confirm = await screen.findByRole("button", { name: "Confirm receipt and close" });
  await userEvent.click(confirm);
  expect(await screen.findByRole("alert")).toHaveTextContent("Not ready to close.");

  await userEvent.click(confirm);

  expect(await screen.findByText("Closed delivered")).toBeVisible();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("hides the new request action without a session", async () => {
  vi.stubGlobal(
    "fetch",
    fetchByUrl([
      ["/api/v1/tickets", { tickets: [] }],
      ["/feedback/requests", { requests: [] }],
    ]),
  );

  renderRequests("/app/requests", null);

  expect(await screen.findByRole("heading", { name: "My Requests" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Open new request" })).not.toBeInTheDocument();
  expect(screen.getByText("MOCK DATA ONLY")).toBeVisible();
});
