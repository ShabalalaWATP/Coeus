import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ProfilePage from "./ProfilePage";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/auth";
import { renderWithProviders } from "../../test/test-utils";

const session: AuthSession = {
  csrfToken: "csrf",
  user: {
    id: "user-1",
    username: "user@example.test",
    displayName: "John McGinn",
    roles: ["Customer"],
    defaultRoute: "/app/requests",
    passwordResetRequired: false,
    permissions: ["user:read_self", "ticket:create", "product:search", "product:download"],
  },
};

const profile = {
  userId: "user-1",
  title: "Joint Operations Liaison Officer",
  specialisms: ["Partner liaison", "Requirement coordination"],
  bio: "Synthetic exercise persona coordinating intelligence requirements.",
  updatedAt: "2026-07-14T10:00:00Z",
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("starts read-only, supports cancel and saves an edited profile", async () => {
  const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
    Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve(
          init?.method === "PUT" ? { ...profile, title: "Senior Requirements Officer" } : profile,
        ),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ProfilePage />, "/account/profile", session);

  expect(await screen.findByRole("heading", { name: "John McGinn" })).toBeVisible();
  expect(await screen.findByText("Joint Operations Liaison Officer")).toBeVisible();
  expect(screen.queryByLabelText("Title")).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Edit profile" }));
  const titleInput = screen.getByLabelText("Title");
  await userEvent.clear(titleInput);
  await userEvent.type(titleInput, "Discarded title");
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByText("Joint Operations Liaison Officer")).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Edit profile" }));
  await userEvent.clear(screen.getByLabelText("Title"));
  await userEvent.type(screen.getByLabelText("Title"), "Senior Requirements Officer");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/users/me/profile",
      expect.objectContaining({
        body: JSON.stringify({
          title: "Senior Requirements Officer",
          specialisms: ["Partner liaison", "Requirement coordination"],
          bio: profile.bio,
        }),
        method: "PUT",
      }),
    ),
  );
  expect(await screen.findByText("Profile saved.")).toBeVisible();
  expect(screen.queryByLabelText("Title")).not.toBeInTheDocument();
});

test("shows a bounded profile loading failure", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable." } }),
    }),
  );

  renderWithProviders(<ProfilePage />, "/account/profile", session);

  expect(
    await screen.findByText("Your profile could not be loaded. Refresh and try again.", undefined, {
      timeout: 5_000,
    }),
  ).toBeVisible();
});

test("renders nothing without a signed-in identity", () => {
  const { container } = renderWithProviders(<ProfilePage />, "/account/profile", null);

  expect(container).toBeEmptyDOMElement();
});

test("describes granted access in the product's own words, not permission strings", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(profile) }),
  );

  renderWithProviders(<ProfilePage />, "/account/profile", session);

  expect(await screen.findByRole("heading", { name: /What you can do/ })).toBeVisible();
  expect(screen.getByText("Raise requests")).toBeVisible();
  expect(screen.getByText("Search holdings")).toBeVisible();
  expect(screen.getByText("Download assets")).toBeVisible();
  // The raw permission never reaches the page.
  expect(screen.queryByText(/product:download/)).not.toBeInTheDocument();
  // Signing in is not a capability worth listing.
  expect(screen.queryByText(/user:read_self/)).not.toBeInTheDocument();
});

test("offers a password change and reports an account that must reset", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(profile) }),
  );

  const { unmount } = renderWithProviders(<ProfilePage />, "/account/profile", session);
  expect(screen.getByRole("link", { name: "Change password" })).toHaveAttribute(
    "href",
    "/account/password",
  );
  expect(screen.getByText("Set")).toBeVisible();
  unmount();

  renderWithProviders(<ProfilePage />, "/account/profile", {
    ...session,
    user: { ...session.user, passwordResetRequired: true },
  });
  expect(screen.getByText("Change required")).toBeVisible();
});

test("reports a save that the server rejected", async () => {
  const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
    init?.method === "PUT"
      ? Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
        })
      : Promise.resolve({ ok: true, json: () => Promise.resolve(profile) }),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ProfilePage />, "/account/profile", session);

  await userEvent.click(await screen.findByRole("button", { name: "Edit profile" }));
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

  // A deliberate rejection surfaces the server's own message.
  expect(await screen.findByRole("alert")).toHaveTextContent("Failed.");
  // The edit stays open so the work is not lost.
  expect(screen.getByLabelText("Title")).toBeVisible();
});

test("shows an unreadable updated date as it stands rather than as Invalid Date", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ...profile, updatedAt: "not-a-date" }),
    }),
  );

  renderWithProviders(<ProfilePage />, "/account/profile", session);

  expect(await screen.findByText(/Updated not-a-date/)).toBeVisible();
});

test("says nothing about capabilities when an account only signs in", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(profile) }),
  );

  renderWithProviders(<ProfilePage />, "/account/profile", {
    ...session,
    user: { ...session.user, permissions: ["auth:login", "user:read_self"] },
  });

  await screen.findByText("Joint Operations Liaison Officer");
  expect(screen.queryByRole("heading", { name: /What you can do/ })).not.toBeInTheDocument();
});

test("hides need-to-know access from accounts that cannot view groups", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(profile) }),
  );

  renderWithProviders(<ProfilePage />, "/account/profile", session);

  await screen.findByText("Joint Operations Liaison Officer");
  expect(screen.queryByRole("heading", { name: /Need-to-know access/ })).not.toBeInTheDocument();
});

test("gives an empty profile useful read-first defaults", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ...profile, bio: "", specialisms: [], title: "" }),
    }),
  );

  renderWithProviders(<ProfilePage />, "/account/profile", session);

  expect(await screen.findByText("No title added")).toBeVisible();
  expect(screen.getByText("No specialisms added")).toBeVisible();
  expect(screen.getByText("Add a short biography for your teammates.")).toBeVisible();
});
