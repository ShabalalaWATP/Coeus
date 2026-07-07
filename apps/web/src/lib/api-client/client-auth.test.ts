import { ApiClient, ApiError, apiRequestJson, setAuthEventHandlers } from "./client";

afterEach(() => {
  setAuthEventHandlers({});
  vi.unstubAllGlobals();
});

test("posts password changes with CSRF protection", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 });
  vi.stubGlobal("fetch", fetchMock);

  await new ApiClient("http://api.test").changePassword(
    { currentPassword: "OldPassword123!", newPassword: "NewPassword123!" },
    "csrf-token",
  );

  expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/v1/auth/password", {
    body: JSON.stringify({ currentPassword: "OldPassword123!", newPassword: "NewPassword123!" }),
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
    method: "POST",
  });
});

test("notifies the unauthorized handler for 401s outside auth endpoints", async () => {
  const onUnauthorized = vi.fn();
  const onPasswordChangeRequired = vi.fn();
  setAuthEventHandlers({ onUnauthorized, onPasswordChangeRequired });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ error: { code: "session_expired", message: "Expired." } }),
    }),
  );

  await expect(apiRequestJson("/api/v1/tickets", { method: "GET" })).rejects.toBeInstanceOf(
    ApiError,
  );

  expect(onUnauthorized).toHaveBeenCalledTimes(1);
  expect(onPasswordChangeRequired).not.toHaveBeenCalled();
});

test("notifies the password-change handler for 403 password_change_required", async () => {
  const onUnauthorized = vi.fn();
  const onPasswordChangeRequired = vi.fn();
  setAuthEventHandlers({ onUnauthorized, onPasswordChangeRequired });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: () =>
        Promise.resolve({
          error: { code: "password_change_required", message: "Change your password." },
        }),
    }),
  );

  await expect(apiRequestJson("/api/v1/tickets", { method: "GET" })).rejects.toBeInstanceOf(
    ApiError,
  );

  expect(onPasswordChangeRequired).toHaveBeenCalledTimes(1);
  expect(onUnauthorized).not.toHaveBeenCalled();
});

test("does not notify auth handlers for auth endpoint failures", async () => {
  const onUnauthorized = vi.fn();
  setAuthEventHandlers({ onUnauthorized });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ error: { code: "invalid_credentials", message: "No." } }),
    }),
  );

  await expect(
    new ApiClient("http://api.test").login({ username: "user@example.test", password: "bad" }),
  ).rejects.toBeInstanceOf(ApiError);

  expect(onUnauthorized).not.toHaveBeenCalled();
});
