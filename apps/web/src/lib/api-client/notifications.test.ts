import { ApiError } from "./client";
import { listNotifications, markNotificationRead } from "./notifications";

afterEach(() => {
  vi.restoreAllMocks();
});

test("lists notifications and marks them read with CSRF protection", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ notifications: [], unread: 0 }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await listNotifications();
  await markNotificationRead("notification-1", "csrf");

  expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8001/api/v1/notifications", {
    credentials: "include",
    method: "GET",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/notifications/notification-1/read",
    { credentials: "include", headers: { "X-CSRF-Token": "csrf" }, method: "POST" },
  );
});

test("converts notification API errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: () =>
        Promise.resolve({ error: { code: "notification_not_found", message: "Missing." } }),
    }),
  );

  await expect(markNotificationRead("notification-1", "csrf")).rejects.toEqual(
    new ApiError(404, "notification_not_found", "Missing."),
  );
});
