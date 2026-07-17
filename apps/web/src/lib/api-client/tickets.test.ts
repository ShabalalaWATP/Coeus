import { ApiError } from "./client";
import {
  addTicketCollaborator,
  chooseCollectOption,
  consentNoMatch,
  confirmTicketDelivery,
  getTicket,
  listTickets,
  listUserDirectory,
  reopenTicketConversation,
  removeTicketCollaborator,
} from "./tickets";

afterEach(() => {
  vi.restoreAllMocks();
});

test("calls collaborator endpoints with CSRF-protected mutations", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ users: [] }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await listUserDirectory("col league");
  await addTicketCollaborator("ticket-1", "colleague@example.test", "editor", "csrf");
  await removeTicketCollaborator("ticket-1", "user-2", "csrf");

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "http://127.0.0.1:8001/api/v1/users/directory?q=col+league",
    {
      credentials: "include",
      method: "GET",
    },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/tickets/ticket-1/collaborators",
    expect.objectContaining({
      body: JSON.stringify({ username: "colleague@example.test", access: "editor" }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "POST",
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/tickets/ticket-1/collaborators/user-2",
    { credentials: "include", headers: { "X-CSRF-Token": "csrf" }, method: "DELETE" },
  );
});

test("confirms delivery with a CSRF-protected mutation", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ id: "ticket-1", state: "CLOSED_DELIVERED" }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await expect(confirmTicketDelivery("ticket-1", "csrf")).resolves.toMatchObject({
    state: "CLOSED_DELIVERED",
  });

  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/tickets/ticket-1/confirm-delivery",
    {
      credentials: "include",
      headers: { "X-CSRF-Token": "csrf" },
      method: "POST",
    },
  );
});

test("reopens intake chat with a CSRF-protected mutation", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ id: "ticket-1", conversationStatus: "open" }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await expect(reopenTicketConversation("ticket-1", "csrf")).resolves.toMatchObject({
    conversationStatus: "open",
  });
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/tickets/ticket-1/conversation/reopen",
    {
      credentials: "include",
      headers: { "X-CSRF-Token": "csrf" },
      method: "POST",
    },
  );
});

test("records no-match consent with a CSRF-protected payload", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ id: "ticket-1", state: "JIOC_REVIEW" }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await expect(consentNoMatch("ticket-1", true, "csrf")).resolves.toMatchObject({
    state: "JIOC_REVIEW",
  });

  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/tickets/ticket-1/no-match-consent",
    {
      body: JSON.stringify({ taskAsNewRequest: true }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "POST",
    },
  );
});

test("records the collect choice with a CSRF-protected payload", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ id: "ticket-1", state: "ANALYST_ASSIGNMENT" }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await expect(chooseCollectOption("ticket-1", true, "csrf")).resolves.toMatchObject({
    state: "ANALYST_ASSIGNMENT",
  });
  await chooseCollectOption("ticket-1", false, "csrf");

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "http://127.0.0.1:8001/api/v1/tickets/ticket-1/collect-choice",
    {
      body: JSON.stringify({ analysed: true }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "POST",
    },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/tickets/ticket-1/collect-choice",
    expect.objectContaining({ body: JSON.stringify({ analysed: false }) }),
  );
});

test("returns a single-ticket detail response when the id matches", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: "ticket-1", state: "COLLECT_CHOICE" }),
    }),
  );

  await expect(getTicket("ticket-1")).resolves.toMatchObject({ state: "COLLECT_CHOICE" });
});

test("rejects a single-ticket detail response for a different ticket", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: "ticket-2", state: "COLLECT_CHOICE" }),
    }),
  );

  await expect(getTicket("ticket-1")).rejects.toThrow(
    "Ticket detail response did not match the requested ticket.",
  );
});

test("throws parsed API errors from ticket endpoints", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: () =>
        Promise.resolve({
          error: { code: "forbidden", message: "Access denied." },
        }),
    }),
  );

  await expect(listTickets()).rejects.toEqual(new ApiError(403, "forbidden", "Access denied."));
});
