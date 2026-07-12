import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AccessGroupAdminPanel } from "./AccessGroupAdminPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const group = {
  id: "acg-1",
  code: "ACG-ONE",
  name: "Regional reporting",
  description: "Controlled products.",
  isMember: false,
  applicationStatus: null,
  applicationId: null,
  canReviewApplications: true,
  canManageAdmins: true,
} as const;

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("shows roster and directory failures without hiding the controls", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable." } }),
    }),
  );

  renderWithProviders(<AccessGroupAdminPanel csrfToken="csrf" groups={[group]} />);
  expect(
    await screen.findByText("Group administrators could not be loaded.", undefined, {
      timeout: 10_000,
    }),
  ).toBeVisible();
  await userEvent.type(screen.getByLabelText("Find an active user"), "alex");
  expect(
    await screen.findByText("The user directory could not be loaded.", undefined, {
      timeout: 10_000,
    }),
  ).toBeVisible();
});

test("explains empty and truncated directory results", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const body = url.endsWith("/admins")
        ? { admins: [{ id: "admin-1", username: "admin@test", displayName: "Admin One" }] }
        : url.includes("query=none")
          ? { users: [], page: 1, pageSize: 20, total: 0, totalPages: 0 }
          : {
              users: [{ id: "user-1", username: "alex@test", displayName: "Alex One" }],
              page: 1,
              pageSize: 20,
              total: 2,
              totalPages: 1,
            };
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    }),
  );

  renderWithProviders(<AccessGroupAdminPanel csrfToken="csrf" groups={[group]} />);
  const search = screen.getByLabelText("Find an active user");
  await userEvent.type(search, "none");
  expect(await screen.findByText("No active users match this search.")).toBeVisible();
  await userEvent.clear(search);
  await userEvent.type(search, "alex");
  expect(await screen.findByText("More users match. Refine the name or username.")).toBeVisible();
});

test("stops roster additions at eight administrators", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          admins: Array.from({ length: 8 }, (_, index) => ({
            id: `admin-${index}`,
            username: `admin-${index}@test`,
            displayName: `Admin ${index}`,
          })),
        }),
    }),
  );

  renderWithProviders(<AccessGroupAdminPanel csrfToken="csrf" groups={[group]} />);
  expect(
    await screen.findByText("This group has reached the limit of 8 administrators."),
  ).toBeVisible();
  expect(screen.queryByLabelText("Find an active user")).not.toBeInTheDocument();
});

test("reports rejected delegated-administrator changes", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "PUT" || init?.method === "DELETE") {
        return Promise.resolve({
          ok: false,
          status: 409,
          json: () => Promise.resolve({ error: { code: "stale", message: "The roster changed." } }),
        });
      }
      const body = url.endsWith("/admins")
        ? {
            admins: [
              { id: "admin-1", username: "admin@test", displayName: "Admin One" },
              { id: "admin-2", username: "second@test", displayName: "Admin Two" },
            ],
          }
        : {
            users: [{ id: "candidate-1", username: "candidate@test", displayName: "Candidate" }],
            page: 1,
            pageSize: 20,
            total: 1,
            totalPages: 1,
          };
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    }),
  );

  renderWithProviders(<AccessGroupAdminPanel csrfToken="csrf" groups={[group]} />);
  await userEvent.type(screen.getByLabelText("Find an active user"), "can");
  await userEvent.click(await screen.findByRole("button", { name: "Add Candidate" }));
  expect(await screen.findByText("The roster changed.")).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Remove Admin Two as group administrator" }),
  );
  expect(await screen.findByText("The roster changed.")).toBeVisible();
});
