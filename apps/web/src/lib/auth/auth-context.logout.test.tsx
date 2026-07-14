import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { AuthApi, AuthSession } from "../api-client/auth";
import { ApiError } from "../api-client/client";
import { previewSession } from "../../test/test-utils";
import { AuthProvider, useAuth } from "./auth-context";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

function LogoutProbe() {
  const { changePassword, login, logout, refreshSession, session, status } = useAuth();
  return (
    <div>
      <p>{status}</p>
      <p>{session?.user.displayName ?? "No user"}</p>
      <button type="button" onClick={() => void logout()}>
        Logout
      </button>
      <button
        type="button"
        onClick={() =>
          void login({ username: "admin@example.test", password: "mock" }).catch(() => undefined)
        }
      >
        Login
      </button>
      <button type="button" onClick={() => void refreshSession().catch(() => undefined)}>
        Refresh
      </button>
      <button
        type="button"
        onClick={() =>
          void changePassword({
            currentPassword: "OldPassword123!",
            newPassword: "NewPassword123!",
          }).catch(() => undefined)
        }
      >
        Change Password
      </button>
    </div>
  );
}

function fakeClient(overrides: Partial<AuthApi>): AuthApi {
  return overrides as AuthApi;
}

function deferredSession() {
  let resolve!: (session: AuthSession) => void;
  const promise = new Promise<AuthSession>((resolver) => {
    resolve = resolver;
  });
  return { promise, resolve };
}

test("keeps failed logout unconfirmed until a retry succeeds", async () => {
  const user = userEvent.setup();
  const clearSensitiveCache = vi.fn();
  const logout = vi
    .fn()
    .mockRejectedValueOnce(new ApiError(500, "server_error", "Audit unavailable."))
    .mockResolvedValueOnce(undefined);
  const client = fakeClient({ logout });

  render(
    <AuthProvider
      authApi={client}
      clearSensitiveCache={clearSensitiveCache}
      initialSession={previewSession}
    >
      <LogoutProbe />
    </AuthProvider>,
  );

  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("logout_unconfirmed")).toBeVisible());
  expect(screen.getByText("No user")).toBeVisible();
  expect(clearSensitiveCache).toHaveBeenCalledTimes(2);
  expect(logout).toHaveBeenLastCalledWith(previewSession.csrfToken);

  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("anonymous")).toBeVisible());
  expect(logout).toHaveBeenCalledTimes(2);
  expect(logout).toHaveBeenLastCalledWith(previewSession.csrfToken);
});

test("refreshes a stale CSRF token without restoring protected session state", async () => {
  const user = userEvent.setup();
  const refreshed: AuthSession = { ...previewSession, csrfToken: "refreshed-csrf" };
  const logout = vi
    .fn()
    .mockRejectedValueOnce(new ApiError(403, "csrf_failed", "CSRF validation failed."))
    .mockResolvedValueOnce(undefined);
  const client = fakeClient({
    getCurrentUser: vi.fn().mockResolvedValue(refreshed),
    logout,
  });

  render(
    <AuthProvider authApi={client} initialSession={previewSession}>
      <LogoutProbe />
    </AuthProvider>,
  );

  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("logout_unconfirmed")).toBeVisible());
  expect(screen.getByText("No user")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("anonymous")).toBeVisible());
  expect(logout.mock.calls).toEqual([[previewSession.csrfToken], [refreshed.csrfToken]]);
});

test("deduplicates concurrent logout requests", async () => {
  const user = userEvent.setup();
  let resolveLogout: (() => void) | undefined;
  const logout = vi.fn(
    () =>
      new Promise<void>((resolve) => {
        resolveLogout = resolve;
      }),
  );
  const client = fakeClient({ logout });

  render(
    <AuthProvider authApi={client} initialSession={previewSession}>
      <LogoutProbe />
    </AuthProvider>,
  );

  const button = screen.getByRole("button", { name: "Logout" });
  await user.click(button);
  await user.click(button);
  expect(logout).toHaveBeenCalledTimes(1);
  resolveLogout?.();
  await waitFor(() => expect(screen.getByText("anonymous")).toBeVisible());
});

test("keeps a reloaded pending logout fail closed until retry", async () => {
  window.localStorage.setItem("coeus.logout.pending", "unconfirmed");
  const user = userEvent.setup();
  const getCurrentUser = vi.fn().mockResolvedValue(previewSession);
  const logout = vi.fn().mockResolvedValue(undefined);
  const changePassword = vi.fn().mockResolvedValue(previewSession);
  const client = fakeClient({ changePassword, getCurrentUser, logout });

  render(
    <AuthProvider authApi={client} initialSession={previewSession}>
      <LogoutProbe />
    </AuthProvider>,
  );

  expect(screen.getByText("logout_unconfirmed")).toBeVisible();
  expect(screen.getByText("No user")).toBeVisible();
  expect(getCurrentUser).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Change Password" }));
  expect(changePassword).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("anonymous")).toBeVisible());
  expect(getCurrentUser).toHaveBeenCalledTimes(1);
  expect(logout).toHaveBeenCalledWith(previewSession.csrfToken);
});

test("does not restore an initial session after cross-tab logout starts", async () => {
  const pendingSession = deferredSession();
  const clearSensitiveCache = vi.fn();

  render(
    <AuthProvider
      authApi={fakeClient({ getCurrentUser: vi.fn().mockReturnValue(pendingSession.promise) })}
      clearSensitiveCache={clearSensitiveCache}
    >
      <LogoutProbe />
    </AuthProvider>,
  );

  expect(screen.getByText("loading")).toBeVisible();
  act(() => {
    window.dispatchEvent(
      new StorageEvent("storage", { key: "coeus.logout.pending", newValue: "pending" }),
    );
  });
  await act(async () => {
    pendingSession.resolve(previewSession);
    await pendingSession.promise;
  });

  expect(screen.getByText("logging_out")).toBeVisible();
  expect(screen.getByText("No user")).toBeVisible();
  expect(clearSensitiveCache).toHaveBeenCalledTimes(1);
});

test("does not restore a stale login after cross-tab logout starts", async () => {
  const user = userEvent.setup();
  const pendingSession = deferredSession();
  const logout = vi.fn().mockResolvedValue(undefined);

  render(
    <AuthProvider
      authApi={fakeClient({
        login: vi.fn().mockReturnValue(pendingSession.promise),
        logout,
      })}
      initialSession={null}
    >
      <LogoutProbe />
    </AuthProvider>,
  );

  await user.click(screen.getByRole("button", { name: "Login" }));
  act(() => {
    window.dispatchEvent(
      new StorageEvent("storage", { key: "coeus.logout.pending", newValue: "pending" }),
    );
    window.dispatchEvent(
      new StorageEvent("storage", { key: "coeus.logout.pending", newValue: null }),
    );
  });
  await act(async () => {
    pendingSession.resolve(previewSession);
    await pendingSession.promise;
  });

  expect(screen.getByText("logout_unconfirmed")).toBeVisible();
  expect(screen.getByText("No user")).toBeVisible();
  expect(window.localStorage.getItem("coeus.logout.pending")).toMatch(/^unconfirmed:/);

  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("anonymous")).toBeVisible());
  expect(logout).toHaveBeenCalledWith(previewSession.csrfToken);
});

test("does not restore a stale refresh after local logout starts", async () => {
  const user = userEvent.setup();
  const pendingSession = deferredSession();
  const logout = vi.fn().mockRejectedValue(new Error("network unavailable"));

  render(
    <AuthProvider
      authApi={fakeClient({
        getCurrentUser: vi.fn().mockReturnValue(pendingSession.promise),
        logout,
      })}
      initialSession={previewSession}
    >
      <LogoutProbe />
    </AuthProvider>,
  );

  await user.click(screen.getByRole("button", { name: "Refresh" }));
  await user.click(screen.getByRole("button", { name: "Logout" }));
  await act(async () => {
    pendingSession.resolve(previewSession);
    await pendingSession.promise;
  });
  await waitFor(() => expect(screen.getByText("logout_unconfirmed")).toBeVisible());

  expect(screen.getByText("No user")).toBeVisible();
  expect(logout).toHaveBeenCalledWith(previewSession.csrfToken);
});

test("quarantines a password rotation that completes after logout", async () => {
  const user = userEvent.setup();
  const pendingSession = deferredSession();
  const rotatedSession = { ...previewSession, csrfToken: "password-rotation-csrf" };
  const logout = vi.fn().mockResolvedValue(undefined);

  render(
    <AuthProvider
      authApi={fakeClient({
        changePassword: vi.fn().mockReturnValue(pendingSession.promise),
        logout,
      })}
      initialSession={previewSession}
    >
      <LogoutProbe />
    </AuthProvider>,
  );

  await user.click(screen.getByRole("button", { name: "Change Password" }));
  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("anonymous")).toBeVisible());
  await act(async () => {
    pendingSession.resolve(rotatedSession);
    await pendingSession.promise;
  });

  expect(screen.getByText("logout_unconfirmed")).toBeVisible();
  expect(screen.getByText("No user")).toBeVisible();
  expect(window.localStorage.getItem("coeus.logout.pending")).toMatch(/^unconfirmed:/);
  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("anonymous")).toBeVisible());
  expect(logout.mock.calls).toEqual([[previewSession.csrfToken], [rotatedSession.csrfToken]]);
});

test("does not let an older current-session 401 clear a newer quarantine", async () => {
  const user = userEvent.setup();
  const pendingLogin = deferredSession();
  const replacementSession = { ...previewSession, csrfToken: "replacement-session-csrf" };
  let rejectCurrentSession!: (error: ApiError) => void;
  const getCurrentUser = vi.fn().mockImplementationOnce(
    () =>
      new Promise<AuthSession>((_resolve, reject) => {
        rejectCurrentSession = reject;
      }),
  );
  const logout = vi.fn().mockResolvedValue(undefined);

  render(
    <AuthProvider
      authApi={fakeClient({
        getCurrentUser,
        login: vi.fn().mockReturnValue(pendingLogin.promise),
        logout,
      })}
      initialSession={null}
    >
      <LogoutProbe />
    </AuthProvider>,
  );

  await user.click(screen.getByRole("button", { name: "Login" }));
  act(() => {
    window.dispatchEvent(
      new StorageEvent("storage", { key: "coeus.logout.pending", newValue: "unconfirmed:other" }),
    );
  });
  await user.click(screen.getByRole("button", { name: "Logout" }));
  await act(async () => {
    pendingLogin.resolve(replacementSession);
    await pendingLogin.promise;
  });
  act(() =>
    rejectCurrentSession(
      new ApiError(401, "not_authenticated", "Earlier cookie snapshot was absent."),
    ),
  );
  await waitFor(() => expect(screen.getByText("logout_unconfirmed")).toBeVisible());

  expect(window.localStorage.getItem("coeus.logout.pending")).toMatch(/^unconfirmed:/);
  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("anonymous")).toBeVisible());
  expect(getCurrentUser).toHaveBeenCalledTimes(1);
  expect(logout).toHaveBeenCalledWith(replacementSession.csrfToken);
});
