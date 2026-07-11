import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AuthenticatedShell } from "./AuthenticatedShell";
import { AppProviders } from "../../app/providers";
import type { AuthApi } from "../../lib/api-client/auth";
import { ApiError } from "../../lib/api-client/client";
import { previewSession } from "../../test/test-utils";

function fakeClient(overrides: Partial<AuthApi>): AuthApi {
  return overrides as AuthApi;
}

test("renders the app shell for authenticated users", () => {
  render(
    <AppProviders initialAuthSession={previewSession}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<AuthenticatedShell />} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );

  expect(screen.getByLabelText("Primary navigation")).toBeVisible();
});

test("redirects anonymous users to login", () => {
  render(
    <AppProviders initialAuthSession={null}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<AuthenticatedShell />} />
          <Route path="/login" element={<p>Login route</p>} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );

  expect(screen.getByText("Login route")).toBeVisible();
});

test("shows loading while checking the backend session", () => {
  render(
    <AppProviders
      authApi={fakeClient({ getCurrentUser: vi.fn().mockReturnValue(new Promise(() => null)) })}
    >
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<AuthenticatedShell />} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );

  expect(screen.getByText("Loading workspace")).toBeVisible();
});

test("forces password changes before any other route", () => {
  render(
    <AppProviders initialAuthSession={{ ...previewSession, passwordResetRequired: true }}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<AuthenticatedShell />} />
          <Route path="/account/password" element={<p>Password route</p>} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );

  expect(screen.getByText("Password route")).toBeVisible();
});

test("redirects expired sessions", async () => {
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
          <Route path="/" element={<AuthenticatedShell />} />
          <Route path="/session-expired" element={<p>Expired route</p>} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );

  expect(await screen.findByText("Expired route")).toBeVisible();
});
