import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { DefaultRouteRedirect } from "./DefaultRouteRedirect";
import { AppProviders } from "../../app/providers";
import type { AuthApi } from "../../lib/api-client/auth";
import { ApiError } from "../../lib/api-client/client";
import { previewSession } from "../../test/test-utils";

function fakeClient(overrides: Partial<AuthApi>): AuthApi {
  return overrides as AuthApi;
}

test("redirects authenticated users to their backend-provided default route", () => {
  render(
    <AppProviders
      initialAuthSession={{
        ...previewSession,
        user: { ...previewSession.user, defaultRoute: "/app/requests" },
      }}
    >
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<DefaultRouteRedirect />} />
          <Route path="/app/requests" element={<p>Requests route</p>} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );

  expect(screen.getByText("Requests route")).toBeVisible();
});

test("redirects anonymous users to login", () => {
  render(
    <AppProviders initialAuthSession={null}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<DefaultRouteRedirect />} />
          <Route path="/login" element={<p>Login route</p>} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );

  expect(screen.getByText("Login route")).toBeVisible();
});

test("shows loading while the current session is being fetched", () => {
  render(
    <AppProviders
      authApi={fakeClient({ getCurrentUser: vi.fn().mockReturnValue(new Promise(() => null)) })}
    >
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<DefaultRouteRedirect />} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );

  expect(screen.getByText("Loading workspace")).toBeVisible();
});

test("redirects expired sessions to the session expired route", async () => {
  render(
    <AppProviders
      authApi={fakeClient({
        getCurrentUser: vi
          .fn()
          .mockRejectedValue(new ApiError(401, "session_expired", "Session expired.")),
      })}
    >
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<DefaultRouteRedirect />} />
          <Route path="/session-expired" element={<p>Expired route</p>} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );

  expect(await screen.findByText("Expired route")).toBeVisible();
});
