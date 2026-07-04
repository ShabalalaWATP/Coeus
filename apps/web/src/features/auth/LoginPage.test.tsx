import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import LoginPage from "./LoginPage";
import { AppProviders } from "../../app/providers";
import { ApiError, type ApiClient } from "../../lib/api-client/client";
import { previewSession } from "../../test/test-utils";

function fakeClient(overrides: Partial<ApiClient>): ApiClient {
  return overrides as ApiClient;
}

function renderLogin(client: ApiClient) {
  return render(
    <AppProviders apiClient={client} initialAuthSession={null}>
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/app/requests" element={<p>Requests route</p>} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );
}

function renderLoginAtState(client: ApiClient, state: { from?: string }) {
  return render(
    <AppProviders apiClient={client} initialAuthSession={null}>
      <MemoryRouter initialEntries={[{ pathname: "/login", state }]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/rfa/queue" element={<p>RFA queue route</p>} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );
}

test("renders secure login controls and toggles password visibility", async () => {
  const user = userEvent.setup();
  renderLogin(fakeClient({ login: vi.fn() }));

  expect(screen.getByText("Private system. Authorised access only.")).toBeVisible();
  expect(screen.getByLabelText("Username")).toBeVisible();
  expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");

  await user.click(screen.getByRole("button", { name: "Show password" }));

  expect(screen.getByLabelText("Password")).toHaveAttribute("type", "text");
});

test("submits credentials and navigates to the backend default route", async () => {
  const user = userEvent.setup();
  const login = vi.fn().mockResolvedValue({
    ...previewSession,
    user: { ...previewSession.user, defaultRoute: "/app/requests" },
  });
  renderLogin(fakeClient({ login }));

  await user.type(screen.getByLabelText("Username"), "admin@example.test");
  await user.type(screen.getByLabelText("Password"), "CoeusLocal1!");
  await user.click(screen.getByRole("button", { name: "Sign in" }));

  await waitFor(() => expect(screen.getByText("Requests route")).toBeVisible());
  expect(login).toHaveBeenCalledWith({
    username: "admin@example.test",
    password: "CoeusLocal1!",
  });
  expect(window.localStorage.getItem("token")).toBeNull();
});

test("honours the route that originally required authentication", async () => {
  const user = userEvent.setup();
  const login = vi.fn().mockResolvedValue({
    ...previewSession,
    user: { ...previewSession.user, defaultRoute: "/app/requests" },
  });
  renderLoginAtState(fakeClient({ login }), { from: "/rfa/queue" });

  await user.type(screen.getByLabelText("Username"), "admin@example.test");
  await user.type(screen.getByLabelText("Password"), "CoeusLocal1!");
  await user.click(screen.getByRole("button", { name: "Sign in" }));

  await waitFor(() => expect(screen.getByText("RFA queue route")).toBeVisible());
});

test("shows validation errors before submitting", async () => {
  const user = userEvent.setup();
  renderLogin(fakeClient({ login: vi.fn() }));

  await user.click(screen.getByRole("button", { name: "Sign in" }));

  expect(await screen.findByText("Enter a valid username.")).toBeVisible();
  expect(screen.getByText("Enter your password.")).toBeVisible();
});

test("shows generic auth errors and locked state", async () => {
  const user = userEvent.setup();
  renderLogin(
    fakeClient({
      login: vi.fn().mockRejectedValue(new ApiError(423, "account_locked", "Locked.")),
    }),
  );

  await user.type(screen.getByLabelText("Username"), "admin@example.test");
  await user.type(screen.getByLabelText("Password"), "wrong");
  await user.click(screen.getByRole("button", { name: "Sign in" }));

  await waitFor(() =>
    expect(
      screen.getByText("Authentication is temporarily locked. Try again later."),
    ).toBeVisible(),
  );
  expect(screen.getByRole("button", { name: "Sign in" })).toBeDisabled();
});

test("shows generic authentication failure for non-lockout errors", async () => {
  const user = userEvent.setup();
  renderLogin(
    fakeClient({
      login: vi
        .fn()
        .mockRejectedValue(new ApiError(401, "authentication_failed", "Authentication failed.")),
    }),
  );

  await user.type(screen.getByLabelText("Username"), "admin@example.test");
  await user.type(screen.getByLabelText("Password"), "wrong");
  await user.click(screen.getByRole("button", { name: "Sign in" }));

  await waitFor(() => expect(screen.getByText("Authentication failed.")).toBeVisible());
});
