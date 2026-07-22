import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AuthProvider, useAuth } from "./auth-context";
import type { AuthApi, AuthSession } from "../api-client/auth";
import { ApiError, apiRequestJson } from "../api-client/client";
import { previewSession } from "../../test/test-utils";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

function AuthProbe() {
  const { login, logout, refreshSession, session, status } = useAuth();
  return (
    <div>
      <p>{status}</p>
      <p>{session?.user.displayName ?? "No user"}</p>
      <p>
        {session?.user.passwordResetRequired === true ? "reset-required" : "reset-not-required"}
      </p>
      <button
        type="button"
        onClick={() =>
          void login({ username: "admin@example.test", password: "mock" }).catch(() => undefined)
        }
      >
        Login
      </button>
      <button type="button" onClick={() => void logout()}>
        Logout
      </button>
      <button type="button" onClick={() => void refreshSession()}>
        Refresh
      </button>
    </div>
  );
}

function fakeClient(overrides: Partial<AuthApi>): AuthApi {
  return overrides as AuthApi;
}

test("loads the current user from the backend", async () => {
  const client = fakeClient({
    getCurrentUser: vi.fn().mockResolvedValue(previewSession),
  });

  render(
    <AuthProvider authApi={client}>
      <AuthProbe />
    </AuthProvider>,
  );

  await waitFor(() => expect(screen.getByText("authenticated")).toBeVisible());
  expect(screen.getByText("Sprint 2 Operator")).toBeVisible();
});

test("marks expired backend sessions distinctly", async () => {
  const client = fakeClient({
    getCurrentUser: vi
      .fn()
      .mockRejectedValue(new ApiError(401, "session_expired", "Session expired.")),
  });

  render(
    <AuthProvider authApi={client}>
      <AuthProbe />
    </AuthProvider>,
  );

  await waitFor(() => expect(screen.getByText("expired")).toBeVisible());
});

test("treats a generic initial session lookup failure as anonymous", async () => {
  const client = fakeClient({
    getCurrentUser: vi.fn().mockRejectedValue(new Error("network unavailable")),
  });

  render(
    <AuthProvider authApi={client}>
      <AuthProbe />
    </AuthProvider>,
  );

  await waitFor(() => expect(screen.getByText("anonymous")).toBeVisible());
});

test("login and logout update session state without local storage tokens", async () => {
  const user = userEvent.setup();
  const nextSession: AuthSession = {
    ...previewSession,
    user: { ...previewSession.user, displayName: "Admin Operator" },
  };
  const logout = vi.fn().mockResolvedValue(undefined);
  const client = fakeClient({
    getCurrentUser: vi.fn(),
    login: vi.fn().mockResolvedValue(nextSession),
    logout,
  });

  render(
    <AuthProvider authApi={client} initialSession={null}>
      <AuthProbe />
    </AuthProvider>,
  );

  await user.click(screen.getByRole("button", { name: "Login" }));
  expect(screen.getByText("Admin Operator")).toBeVisible();

  await user.click(screen.getByRole("button", { name: "Logout" }));
  expect(logout).toHaveBeenCalledWith(nextSession.csrfToken);
  expect(window.localStorage.getItem("token")).toBeNull();
  expect(window.localStorage.getItem("coeus_session")).toBeNull();
});

test("blocks login while a persisted logout remains unconfirmed", async () => {
  window.localStorage.setItem("coeus.logout.pending", "unconfirmed");
  const user = userEvent.setup();
  const login = vi.fn().mockResolvedValue(previewSession);

  render(
    <AuthProvider authApi={fakeClient({ login })} initialSession={previewSession}>
      <AuthProbe />
    </AuthProvider>,
  );

  await user.click(screen.getByRole("button", { name: "Login" }));
  expect(login).not.toHaveBeenCalled();
  expect(screen.getByText("logout_unconfirmed")).toBeVisible();
});

test("confirms session absence when logout or its private refresh returns 401", async () => {
  const user = userEvent.setup();
  const direct401 = fakeClient({
    getCurrentUser: vi.fn().mockRejectedValue(new ApiError(401, "not_authenticated", "Gone.")),
    logout: vi.fn().mockRejectedValue(new ApiError(401, "not_authenticated", "Gone.")),
  });
  const first = render(
    <AuthProvider authApi={direct401} initialSession={previewSession}>
      <AuthProbe />
    </AuthProvider>,
  );
  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("expired")).toBeVisible());
  first.unmount();

  const refreshed401 = fakeClient({
    getCurrentUser: vi.fn().mockRejectedValue(new ApiError(401, "not_authenticated", "Gone.")),
    logout: vi.fn().mockRejectedValue(new ApiError(500, "server_error", "Failed.")),
  });
  render(
    <AuthProvider authApi={refreshed401} initialSession={previewSession}>
      <AuthProbe />
    </AuthProvider>,
  );
  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("expired")).toBeVisible());
});

test("confirms an already absent reloaded session without a CSRF token", async () => {
  window.localStorage.setItem("coeus.logout.pending", "unconfirmed");
  const user = userEvent.setup();
  const getCurrentUser = vi.fn().mockRejectedValue(new ApiError(401, "not_authenticated", "Gone."));

  render(
    <AuthProvider authApi={fakeClient({ getCurrentUser })} initialSession={null}>
      <AuthProbe />
    </AuthProvider>,
  );
  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("expired")).toBeVisible());
});

test("keeps fail-closed in memory when browser storage is unavailable", async () => {
  const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("storage unavailable");
  });
  const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("storage unavailable");
  });
  const user = userEvent.setup();
  const logout = vi.fn().mockRejectedValue(new Error("network unavailable"));

  render(
    <AuthProvider
      authApi={fakeClient({ getCurrentUser: vi.fn().mockRejectedValue(new Error()), logout })}
      initialSession={previewSession}
    >
      <AuthProbe />
    </AuthProvider>,
  );
  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("logout_unconfirmed")).toBeVisible());
  expect(getItem).toHaveBeenCalled();
  expect(setItem).toHaveBeenCalled();
});

test("synchronises logout state from another browser tab", () => {
  const clearSensitiveCache = vi.fn();

  render(
    <AuthProvider
      authApi={fakeClient({})}
      clearSensitiveCache={clearSensitiveCache}
      initialSession={previewSession}
    >
      <AuthProbe />
    </AuthProvider>,
  );

  expect(screen.getByText("authenticated")).toBeVisible();
  act(() => {
    window.dispatchEvent(new StorageEvent("storage", { key: "unrelated", newValue: "pending" }));
  });
  expect(screen.getByText("authenticated")).toBeVisible();

  act(() => {
    window.dispatchEvent(
      new StorageEvent("storage", { key: "coeus.logout.pending", newValue: "pending" }),
    );
  });
  expect(screen.getByText("logging_out")).toBeVisible();
  expect(screen.getByText("No user")).toBeVisible();

  act(() => {
    window.dispatchEvent(
      new StorageEvent("storage", { key: "coeus.logout.pending", newValue: "unconfirmed" }),
    );
  });
  expect(screen.getByText("logout_unconfirmed")).toBeVisible();

  act(() => {
    window.dispatchEvent(
      new StorageEvent("storage", { key: "coeus.logout.pending", newValue: null }),
    );
  });
  expect(screen.getByText("anonymous")).toBeVisible();
  expect(clearSensitiveCache).toHaveBeenCalledTimes(3);
});

test("moves an authenticated session to expired when any API call returns 401", async () => {
  const clearSensitiveCache = vi.fn();
  const client = fakeClient({});
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ error: { code: "session_expired", message: "Expired." } }),
    }),
  );

  render(
    <AuthProvider
      clearSensitiveCache={clearSensitiveCache}
      authApi={client}
      initialSession={previewSession}
    >
      <AuthProbe />
    </AuthProvider>,
  );

  expect(screen.getByText("authenticated")).toBeVisible();
  await act(async () => {
    await expect(apiRequestJson("/api/v1/tickets", { method: "GET" })).rejects.toBeInstanceOf(
      ApiError,
    );
  });

  await waitFor(() => expect(screen.getByText("expired")).toBeVisible());
  expect(screen.getByText("No user")).toBeVisible();
  expect(clearSensitiveCache).toHaveBeenCalled();
});

test("flags the session for a forced password change on 403 password_change_required", async () => {
  const client = fakeClient({});
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

  render(
    <AuthProvider authApi={client} initialSession={previewSession}>
      <AuthProbe />
    </AuthProvider>,
  );

  expect(screen.getByText("reset-not-required")).toBeVisible();
  await act(async () => {
    await expect(apiRequestJson("/api/v1/tickets", { method: "GET" })).rejects.toBeInstanceOf(
      ApiError,
    );
  });

  await waitFor(() => expect(screen.getByText("reset-required")).toBeVisible());
  expect(screen.getByText("authenticated")).toBeVisible();
});

test("refreshes the session from the backend on demand", async () => {
  const refreshedSession: AuthSession = {
    ...previewSession,
    user: {
      ...previewSession.user,
      displayName: "Refreshed Operator",
      passwordResetRequired: false,
    },
  };
  const client = fakeClient({
    getCurrentUser: vi.fn().mockResolvedValue(refreshedSession),
  });

  render(
    <AuthProvider authApi={client} initialSession={previewSession}>
      <AuthProbe />
    </AuthProvider>,
  );

  await userEvent.click(screen.getByRole("button", { name: "Refresh" }));

  await waitFor(() => expect(screen.getByText("Refreshed Operator")).toBeVisible());
  expect(screen.getByText("authenticated")).toBeVisible();
});

test("rejects auth hook usage outside provider", () => {
  const originalError = console.error;
  console.error = vi.fn();

  expect(() => render(<AuthProbe />)).toThrow("useAuth must be used within AuthProvider.");

  console.error = originalError;
});
