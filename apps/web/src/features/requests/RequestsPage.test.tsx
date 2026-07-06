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
  expect(screen.getByText("No chat transcript")).toBeVisible();
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
  expect(screen.getByText("Details the assistant needs")).toBeVisible();
  expect(screen.getByText("5 of 7 captured from the conversation.")).toBeVisible();
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

  expect((await screen.findAllByText("RFI SEARCHING")).length).toBeGreaterThan(0);
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
