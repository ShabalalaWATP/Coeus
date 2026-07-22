import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import AcgAdminPage from "./AcgAdminPage";
import { AppProviders } from "../../app/providers";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/auth";
import { previewSession, renderWithProviders } from "../../test/test-utils";

function renderAcgRoute(initialPath: string) {
  window.history.pushState({}, "Test page", initialPath);
  return render(
    <AppProviders initialAuthSession={previewSession}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/admin/acgs" element={<AcgAdminPage />} />
          <Route path="/admin/acgs/:acgId" element={<AcgAdminPage />} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );
}

const acg = {
  id: "acg-alpha",
  code: "ACG-ALPHA",
  name: "Alpha Regional",
  description: "Regional access group",
  ownerUserId: null,
  isActive: true,
  memberUserIds: ["user-alpha"],
  members: [{ id: "user-alpha", displayName: "Alpha Analyst", username: "alpha@example.test" }],
};

beforeEach(() => {
  vi.stubGlobal(
    "confirm",
    vi.fn(() => true),
  );
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders access control groups and allows creating a group", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ acgs: [acg] }) })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          ...acg,
          id: "acg-bravo",
          code: "ACG-BRAVO",
          name: "Bravo Collection",
        }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          acgs: [acg, { ...acg, id: "acg-bravo", code: "ACG-BRAVO", name: "Bravo Collection" }],
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AcgAdminPage />, "/admin/acgs");

  expect(screen.getByRole("link", { name: "Back to Admin" })).toHaveAttribute(
    "href",
    "/admin/overview",
  );
  expect(await screen.findByRole("button", { name: /ACG-ALPHA Alpha Regional/i })).toBeVisible();
  const createForm = within(screen.getByRole("form", { name: "Create access control group" }));
  await userEvent.type(createForm.getByLabelText("Code"), "ACG-BRAVO");
  await userEvent.type(createForm.getByLabelText("Name"), "Bravo Collection");
  await userEvent.type(createForm.getByLabelText("Description"), "Collection access group");
  await userEvent.click(createForm.getByRole("button", { name: /Create/i }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/acgs",
      expect.objectContaining({
        body: JSON.stringify({
          code: "ACG-BRAVO",
          name: "Bravo Collection",
          description: "Collection access group",
        }),
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
        method: "POST",
      }),
    ),
  );
});

test("updates selected access control group membership", async () => {
  const fetchMock = vi.fn((url: string, init?: RequestInit) =>
    Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve(
          url.includes("/admin-directory")
            ? {
                users: [
                  {
                    id: "user-bravo",
                    username: "bravo@example.test",
                    displayName: "Bravo User",
                  },
                ],
              }
            : init?.method === "POST"
              ? { ...acg, memberUserIds: ["user-alpha", "user-bravo"] }
              : { acgs: [acg] },
        ),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AcgAdminPage />, "/admin/acgs");

  expect(await screen.findByRole("heading", { name: "Alpha Regional" })).toBeVisible();
  await userEvent.type(screen.getByLabelText("Search active users"), "Bravo");
  await userEvent.click(
    await screen.findByRole("button", { name: "Bravo User (bravo@example.test)" }),
  );
  await userEvent.click(screen.getByRole("button", { name: /Add member/i }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/acgs/acg-alpha/members",
      expect.objectContaining({
        body: JSON.stringify({ userId: "user-bravo" }),
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
        method: "POST",
      }),
    ),
  );
});

test("shows scoped member identities before any directory search", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ acgs: [acg] }),
    }),
  );
  renderWithProviders(<AcgAdminPage />, "/admin/acgs");
  expect(await screen.findByText("Alpha Analyst")).toBeVisible();
  expect(screen.getByText("alpha@example.test")).toBeVisible();
});

test("hides mutation forms from view-only access", async () => {
  const viewOnlySession: AuthSession = {
    csrfToken: "test-csrf-token",
    user: {
      id: "team-user",
      username: "rfa.team@example.test",
      displayName: "RFA Team Member",
      roles: ["RFA Team Member"],
      defaultRoute: "/rfa/products",
      passwordResetRequired: false,
      permissions: ["acg:view"],
    },
  };
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ acgs: [acg] }) }),
  );

  renderWithProviders(<AcgAdminPage />, "/admin/acgs", viewOnlySession);

  expect(await screen.findByRole("heading", { name: "Alpha Regional" })).toBeVisible();
  expect(screen.getByText("You have read-only access to access control groups.")).toBeVisible();
  expect(
    screen.queryByRole("form", { name: "Create access control group" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Search active users")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Save/i })).not.toBeInTheDocument();
});

test("honours the acgId route parameter when selecting a group", async () => {
  const bravoAcg = {
    ...acg,
    id: "acg-bravo",
    code: "ACG-BRAVO",
    name: "Bravo Collection",
  };
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ acgs: [acg, bravoAcg] }) }),
  );

  renderAcgRoute("/admin/acgs/acg-bravo");

  expect(await screen.findByRole("heading", { name: "Bravo Collection" })).toBeVisible();
  expect(
    screen.queryByText("The requested access group was not found.", { exact: false }),
  ).not.toBeInTheDocument();
});

test("initialises the edit form from a routed inactive group", async () => {
  const bravoAcg = {
    ...acg,
    id: "acg-bravo",
    code: "ACG-BRAVO",
    name: "Bravo Collection",
    isActive: false,
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ acgs: [acg, bravoAcg] }) })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ ...bravoAcg, name: "Bravo Reviewed" }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          acgs: [acg, { ...bravoAcg, name: "Bravo Reviewed" }],
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderAcgRoute("/admin/acgs/acg-bravo");

  expect(await screen.findByRole("heading", { name: "Bravo Collection" })).toBeVisible();
  const selectedGroup = within(screen.getByLabelText("Selected access group"));
  await waitFor(() => expect(selectedGroup.getByLabelText("Name")).toHaveValue("Bravo Collection"));
  expect(selectedGroup.getByLabelText("Active")).not.toBeChecked();
  await userEvent.clear(selectedGroup.getByLabelText("Name"));
  await userEvent.type(selectedGroup.getByLabelText("Name"), "Bravo Reviewed");
  await userEvent.click(selectedGroup.getByRole("button", { name: /Save/i }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/acgs/acg-bravo",
      expect.objectContaining({
        body: JSON.stringify({ name: "Bravo Reviewed", isActive: false }),
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
        method: "PATCH",
      }),
    ),
  );
});

test("notes when the requested access group does not exist", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ acgs: [acg] }) }),
  );

  renderAcgRoute("/admin/acgs/acg-missing");

  expect(
    await screen.findByText(
      "The requested access group was not found. Showing the first available group instead.",
    ),
  ).toBeVisible();
  expect(screen.getByRole("heading", { name: "Alpha Regional" })).toBeVisible();
});

test("renders an access groups error state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );

  renderWithProviders(<AcgAdminPage />, "/admin/acgs");

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
});

test("selects and updates access control group details", async () => {
  const bravoAcg = {
    ...acg,
    id: "acg-bravo",
    code: "ACG-BRAVO",
    name: "Bravo Collection",
    isActive: false,
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ acgs: [acg, bravoAcg] }) })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ ...bravoAcg, name: "Bravo Updated", isActive: true }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          acgs: [acg, { ...bravoAcg, name: "Bravo Updated", isActive: true }],
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AcgAdminPage />, "/admin/acgs");

  await userEvent.click(await screen.findByRole("button", { name: /ACG-BRAVO Bravo Collection/i }));
  const selectedGroup = within(screen.getByLabelText("Selected access group"));
  await userEvent.clear(selectedGroup.getByLabelText("Name"));
  await userEvent.type(selectedGroup.getByLabelText("Name"), "Bravo Updated");
  await userEvent.click(selectedGroup.getByLabelText("Active"));
  await userEvent.click(selectedGroup.getByRole("button", { name: /Save/i }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/acgs/acg-bravo",
      expect.objectContaining({
        body: JSON.stringify({ name: "Bravo Updated", isActive: true }),
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
        method: "PATCH",
      }),
    ),
  );
});
