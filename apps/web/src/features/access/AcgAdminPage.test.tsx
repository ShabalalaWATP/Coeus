import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AcgAdminPage from "./AcgAdminPage";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/client";
import { renderWithProviders } from "../../test/test-utils";

const acg = {
  id: "acg-alpha",
  code: "ACG-ALPHA",
  name: "Alpha Regional",
  description: "Regional access group",
  ownerUserId: null,
  isActive: true,
  memberUserIds: ["user-alpha"],
};

beforeEach(() => {
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

  expect(await screen.findByRole("button", { name: /ACG-ALPHA Alpha Regional/i })).toBeVisible();
  const createForm = within(screen.getByRole("form", { name: "Create access control group" }));
  await userEvent.type(createForm.getByLabelText("Code"), "ACG-BRAVO");
  await userEvent.type(createForm.getByLabelText("Name"), "Bravo Collection");
  await userEvent.type(createForm.getByLabelText("Description"), "Collection access group");
  await userEvent.click(createForm.getByRole("button", { name: /Create/i }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
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
  );
});

test("updates selected access control group membership", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ acgs: [acg] }) })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ ...acg, memberUserIds: ["user-alpha", "user-bravo"] }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          acgs: [{ ...acg, memberUserIds: ["user-alpha", "user-bravo"] }],
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AcgAdminPage />, "/admin/acgs");

  expect(await screen.findByRole("heading", { name: "Alpha Regional" })).toBeVisible();
  await userEvent.type(screen.getByLabelText("User ID"), "user-bravo");
  await userEvent.click(screen.getByRole("button", { name: /Add member/i }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/acgs/acg-alpha/members",
    expect.objectContaining({
      body: JSON.stringify({ userId: "user-bravo" }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
      method: "POST",
    }),
  );
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
  expect(screen.queryByLabelText("User ID")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Save/i })).not.toBeInTheDocument();
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

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/acgs/acg-bravo",
    expect.objectContaining({
      body: JSON.stringify({ name: "Bravo Updated", isActive: true }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
      method: "PATCH",
    }),
  );
});
