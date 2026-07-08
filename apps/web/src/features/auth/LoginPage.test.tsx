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
  await user.click(screen.getByRole("button", { name: "Sign in to Istari" }));

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
  await user.click(screen.getByRole("button", { name: "Sign in to Istari" }));

  await waitFor(() => expect(screen.getByText("RFA queue route")).toBeVisible());
});

test("shows validation errors before submitting", async () => {
  const user = userEvent.setup();
  renderLogin(fakeClient({ login: vi.fn() }));

  await user.click(screen.getByRole("button", { name: "Sign in to Istari" }));

  expect(await screen.findByText("Enter a valid username.")).toBeVisible();
  expect(screen.getByText("Enter your password.")).toBeVisible();
});

test("introduces Istari and switches between sign in and request access", async () => {
  const user = userEvent.setup();
  renderLogin(fakeClient({ login: vi.fn() }));

  expect(screen.getByRole("heading", { name: "Istari" })).toBeVisible();
  expect(screen.getByAltText("Istari logo")).toBeVisible();
  expect(screen.getByText("Task. Assess. Deliver.")).toBeVisible();

  await user.click(screen.getByRole("button", { name: "Request access" }));
  expect(screen.getByRole("heading", { name: "Request access" })).toBeVisible();
  expect(screen.getByLabelText("Display name")).toBeVisible();

  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(screen.getByRole("heading", { name: "Sign in" })).toBeVisible();
  expect(screen.getByLabelText("Username")).toBeVisible();
});

test("shows lockout errors without trapping the retry path", async () => {
  const user = userEvent.setup();
  const login = vi.fn().mockRejectedValue(new ApiError(423, "account_locked", "Locked."));
  renderLogin(
    fakeClient({
      login,
    }),
  );

  await user.type(screen.getByLabelText("Username"), "admin@example.test");
  await user.type(screen.getByLabelText("Password"), "wrong");
  await user.click(screen.getByRole("button", { name: "Sign in to Istari" }));

  await waitFor(() =>
    expect(
      screen.getByText("Authentication is temporarily locked. Try again later."),
    ).toBeVisible(),
  );
  await user.click(screen.getByRole("button", { name: "Sign in to Istari" }));

  expect(screen.getByRole("button", { name: "Sign in to Istari" })).toBeEnabled();
  expect(login).toHaveBeenCalledTimes(2);
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
  await user.click(screen.getByRole("button", { name: "Sign in to Istari" }));

  await waitFor(() => expect(screen.getByText("Authentication failed.")).toBeVisible());
});
