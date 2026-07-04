import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AuthProvider, useAuth } from "./auth-context";
import { ApiError, type ApiClient, type AuthSession } from "../api-client/client";
import { previewSession } from "../../test/test-utils";

function AuthProbe() {
  const { login, logout, session, status } = useAuth();
  return (
    <div>
      <p>{status}</p>
      <p>{session?.user.displayName ?? "No user"}</p>
      <button
        type="button"
        onClick={() => void login({ username: "admin@example.test", password: "mock" })}
      >
        Login
      </button>
      <button type="button" onClick={() => void logout()}>
        Logout
      </button>
    </div>
  );
}

function fakeClient(overrides: Partial<ApiClient>): ApiClient {
  return overrides as ApiClient;
}

test("loads the current user from the backend", async () => {
  const client = fakeClient({
    getCurrentUser: vi.fn().mockResolvedValue(previewSession),
  });

  render(
    <AuthProvider client={client}>
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
    <AuthProvider client={client}>
      <AuthProbe />
    </AuthProvider>,
  );

  await waitFor(() => expect(screen.getByText("expired")).toBeVisible());
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
    <AuthProvider client={client} initialSession={null}>
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

test("rejects auth hook usage outside provider", () => {
  const originalError = console.error;
  console.error = vi.fn();

  expect(() => render(<AuthProbe />)).toThrow("useAuth must be used within AuthProvider.");

  console.error = originalError;
});
