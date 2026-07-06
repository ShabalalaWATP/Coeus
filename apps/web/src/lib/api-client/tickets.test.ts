import { ApiError } from "./client";
import {
  addTicketCollaborator,
  listTickets,
  listUserDirectory,
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

  await listUserDirectory();
  await addTicketCollaborator("ticket-1", "colleague@example.test", "editor", "csrf");
  await removeTicketCollaborator("ticket-1", "user-2", "csrf");

  expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8001/api/v1/users/directory", {
    credentials: "include",
    method: "GET",
  });
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
