import { defaultAuthApi, type AuthSession } from "./auth";
import { ApiError, apiRequestJson, setAuthEventHandlers } from "./client";
import { previewSession } from "../../test/test-utils";

afterEach(() => {
  setAuthEventHandlers({});
  vi.unstubAllGlobals();
});

const { changePassword, getCurrentUser, login, logout } = defaultAuthApi;

test("posts login payloads with credentials included", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(previewSession),
  });
  vi.stubGlobal("fetch", fetchMock);

  await login({ username: "admin@example.test", password: "CoeusLocal1!" });

  expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8001/api/v1/auth/login", {
    body: JSON.stringify({ username: "admin@example.test", password: "CoeusLocal1!" }),
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
});

test("reads the current user and sends csrf for logout", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(previewSession) })
    .mockResolvedValueOnce({ ok: true });
  vi.stubGlobal("fetch", fetchMock);

  await expect(getCurrentUser()).resolves.toEqual(previewSession);
  await logout("csrf-token");

  expect(fetchMock).toHaveBeenNthCalledWith(2, "http://127.0.0.1:8001/api/v1/auth/logout", {
    credentials: "include",
    headers: { "X-CSRF-Token": "csrf-token" },
    method: "POST",
  });
});

test("posts password changes with CSRF protection", async () => {
  const changedSession: AuthSession = { ...previewSession, csrfToken: "csrf-after-change" };
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(changedSession),
  });
  vi.stubGlobal("fetch", fetchMock);

  await expect(
    changePassword(
      { currentPassword: "OldPassword123!", newPassword: "NewPassword123!" },
      "csrf-token",
    ),
  ).resolves.toEqual(changedSession);

  expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8001/api/v1/auth/password", {
    body: JSON.stringify({ currentPassword: "OldPassword123!", newPassword: "NewPassword123!" }),
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
    method: "POST",
  });
});

test("throws parsed API errors on password-change failures", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: () =>
        Promise.resolve({
          error: { code: "invalid_current_password", message: "Current password is incorrect." },
        }),
    }),
  );

  await expect(
    changePassword(
      { currentPassword: "OldPassword123!", newPassword: "NewPassword123!" },
      "csrf-token",
    ),
  ).rejects.toEqual(
    new ApiError(403, "invalid_current_password", "Current password is incorrect."),
  );
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

test("notifies the password-change handler for its protected-endpoint error", async () => {
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

  await expect(login({ username: "user@example.test", password: "bad" })).rejects.toBeInstanceOf(
    ApiError,
  );
  expect(onUnauthorized).not.toHaveBeenCalled();
});
