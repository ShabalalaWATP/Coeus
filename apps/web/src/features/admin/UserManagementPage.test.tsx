import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import UserManagementPage from "./UserManagementPage";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const adminUser = {
  id: "preview-user",
  username: "admin@example.test",
  displayName: "Admin Operator",
  roles: ["Administrator"],
  clearanceLevel: 5,
  isActive: true,
};

const analystUser = {
  id: "analyst-user",
  username: "analyst@example.test",
  displayName: "Analyst Operator",
  roles: ["Intelligence Analyst"],
  clearanceLevel: 3,
  isActive: true,
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders users and applies role, clearance and status changes", async () => {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.endsWith("/admin/users")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ users: [adminUser, analystUser] }),
      });
    }
    if (url.endsWith("/analyst-user/roles")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            ...analystUser,
            roles: ["Intelligence Analyst", "Quality Control Manager"],
          }),
      });
    }
    if (url.endsWith("/analyst-user/clearance")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ...analystUser, clearanceLevel: 4 }),
      });
    }
    if (url.endsWith("/analyst-user/status")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ...analystUser, isActive: false }),
      });
    }
    if (url.endsWith("/analyst-user/credential-reset")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ temporaryCredential: "Istari-temporary" }),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}), init });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<UserManagementPage />, "/admin/users");

  const analystRow = (await screen.findByText("Analyst Operator")).closest("article");
  expect(analystRow).not.toBeNull();
  expect(screen.getByText("Signed-in account changes are blocked.")).toBeVisible();

  await userEvent.click(within(analystRow!).getByLabelText("Quality Control Manager"));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/admin/users/analyst-user/roles",
      expect.objectContaining({
        body: JSON.stringify({
          roles: ["Intelligence Analyst", "Quality Control Manager"],
        }),
        method: "PUT",
      }),
    ),
  );

  await userEvent.selectOptions(within(analystRow!).getByLabelText("Clearance"), "4");
  await userEvent.click(within(analystRow!).getByLabelText("Active account"));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/admin/users/analyst-user/status",
      expect.objectContaining({
        body: JSON.stringify({ isActive: false }),
        method: "PUT",
      }),
    ),
  );
  await userEvent.click(within(analystRow!).getByRole("button", { name: "Reset credential" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/admin/users/analyst-user/credential-reset",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(await screen.findByText("Istari-temporary")).toBeVisible();
});

test("refuses to remove the last role and explains why", async () => {
  const fetchMock = vi.fn((url: string) => {
    if (url.endsWith("/admin/users")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ users: [analystUser] }),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<UserManagementPage />, "/admin/users");

  await userEvent.click(await screen.findByLabelText("Intelligence Analyst"));

  expect(await screen.findByText("An account must keep at least one role.")).toBeVisible();
  expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining("/roles"), expect.anything());
  expect(screen.getByLabelText("Intelligence Analyst")).toBeChecked();
});

test("shows an actionable error when a user update fails", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.endsWith("/admin/users")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ users: [analystUser] }),
        });
      }
      return Promise.resolve({
        ok: false,
        status: 409,
        json: () => Promise.resolve({ error: { code: "user_update_failed", message: "Failed." } }),
      });
    }),
  );

  renderWithProviders(<UserManagementPage />, "/admin/users");

  await userEvent.selectOptions(await screen.findByLabelText("Clearance"), "4");

  expect(
    await screen.findByText("The user change could not be saved. Refresh and try again."),
  ).toBeVisible();
});
