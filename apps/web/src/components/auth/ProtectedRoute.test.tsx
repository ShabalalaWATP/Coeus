import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ProtectedRoute } from "./ProtectedRoute";
import { AppProviders } from "../../app/providers";
import type { AuthApi, AuthSession } from "../../lib/api-client/auth";
import { ApiError } from "../../lib/api-client/client";
import { previewSession } from "../../test/test-utils";

function fakeClient(overrides: Partial<AuthApi>): AuthApi {
  return overrides as AuthApi;
}

function renderGuardedRoute(initialAuthSession: AuthSession | null, path = "/admin/overview") {
  return render(
    <AppProviders initialAuthSession={initialAuthSession}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/admin/overview"
            element={
              <ProtectedRoute requiredPermissions={["system:configure"]}>
                <p>Protected admin</p>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<p>Login route</p>} />
          <Route path="/forbidden" element={<p>Forbidden route</p>} />
          <Route path="/session-expired" element={<p>Expired route</p>} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );
}

test("allows access when the session has the required permission", () => {
  renderGuardedRoute(previewSession);

  expect(screen.getByText("Protected admin")).toBeVisible();
});

test("redirects unauthenticated users to login", () => {
  renderGuardedRoute(null);

  expect(screen.getByText("Login route")).toBeVisible();
});

test("redirects authenticated users without permission to forbidden", () => {
  renderGuardedRoute({
    ...previewSession,
    user: { ...previewSession.user, permissions: ["ticket:read_own"] },
  });

  expect(screen.getByText("Forbidden route")).toBeVisible();
});

test("shows loading while protected route session state is loading", () => {
  render(
    <AppProviders
      authApi={fakeClient({ getCurrentUser: vi.fn().mockReturnValue(new Promise(() => null)) })}
    >
      <MemoryRouter initialEntries={["/admin/overview"]}>
        <Routes>
          <Route
            path="/admin/overview"
            element={
              <ProtectedRoute requiredPermissions={["system:configure"]}>
                <p>Protected admin</p>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );

  expect(screen.getByText("Loading workspace")).toBeVisible();
});

test("redirects expired sessions from protected routes", async () => {
  render(
    <AppProviders
      authApi={fakeClient({
        getCurrentUser: vi
          .fn()
          .mockRejectedValue(new ApiError(401, "session_expired", "Session expired.")),
      })}
    >
      <MemoryRouter initialEntries={["/admin/overview"]}>
        <Routes>
          <Route
            path="/admin/overview"
            element={
              <ProtectedRoute requiredPermissions={["system:configure"]}>
                <p>Protected admin</p>
              </ProtectedRoute>
            }
          />
          <Route path="/session-expired" element={<p>Expired route</p>} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );

  expect(await screen.findByText("Expired route")).toBeVisible();
});
