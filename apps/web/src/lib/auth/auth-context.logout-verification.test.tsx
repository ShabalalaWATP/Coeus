import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { AuthApi, AuthSession } from "../api-client/auth";
import { ApiError } from "../api-client/client";
import { previewSession } from "../../test/test-utils";
import { AuthProvider, useAuth } from "./auth-context";

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

function LogoutProbe() {
  const { logout, status } = useAuth();
  return (
    <div>
      <p>{status}</p>
      <button type="button" onClick={() => void logout()}>
        Logout
      </button>
    </div>
  );
}

test("does not let logout verification clear a newer cross-tab quarantine", async () => {
  const user = userEvent.setup();
  let rejectVerification!: (error: ApiError) => void;
  const verification = new Promise<AuthSession>((_resolve, reject) => {
    rejectVerification = reject;
  });
  const getCurrentUser = vi.fn().mockReturnValue(verification);
  const authApi = {
    getCurrentUser,
    logout: vi.fn().mockRejectedValue(new Error("network unavailable")),
  } as unknown as AuthApi;

  render(
    <AuthProvider authApi={authApi} initialSession={previewSession}>
      <LogoutProbe />
    </AuthProvider>,
  );

  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(getCurrentUser).toHaveBeenCalledTimes(1));
  act(() => {
    window.dispatchEvent(
      new StorageEvent("storage", {
        key: "coeus.logout.pending",
        newValue: "unconfirmed:other-tab",
      }),
    );
  });
  await act(async () => {
    rejectVerification(new ApiError(401, "not_authenticated", "Earlier session was absent."));
    await verification.catch(() => undefined);
  });

  await waitFor(() => expect(screen.getByText("logout_unconfirmed")).toBeVisible());
  expect(window.localStorage.getItem("coeus.logout.pending")).toMatch(/^unconfirmed:/);
});

test("keeps logout quarantined when a tokenless verification cannot reach the server", async () => {
  window.localStorage.setItem("coeus.logout.pending", "unconfirmed");
  const user = userEvent.setup();
  const getCurrentUser = vi.fn().mockRejectedValue(new Error("network unavailable"));
  const logout = vi.fn();
  const authApi = { getCurrentUser, logout } as unknown as AuthApi;

  render(
    <AuthProvider authApi={authApi} initialSession={null}>
      <LogoutProbe />
    </AuthProvider>,
  );

  await user.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByText("logout_unconfirmed")).toBeVisible());

  expect(getCurrentUser).toHaveBeenCalledTimes(1);
  expect(logout).not.toHaveBeenCalled();
  expect(window.localStorage.getItem("coeus.logout.pending")).toMatch(/^unconfirmed:/);
});
