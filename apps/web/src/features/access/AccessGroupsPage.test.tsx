import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AccessGroupsPage from "./AccessGroupsPage";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/auth";
import { renderWithProviders } from "../../test/test-utils";

const session: AuthSession = {
  csrfToken: "csrf",
  user: {
    id: "user-1",
    username: "requester@example.test",
    displayName: "Requesting User",
    roles: ["Requester"],
    defaultRoute: "/app/requests",
    permissions: ["user:read_self"],
  },
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("lets an authenticated user apply to an active group", async () => {
  const fetchMock = vi.fn((url: string, init?: RequestInit) =>
    Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve(
          url.includes("/acg-applications")
            ? { applications: [] }
            : init?.method === "POST"
              ? { id: "application-1", status: "pending" }
              : {
                  acgs: [
                    {
                      id: "acg-1",
                      code: "ACG-ONE",
                      name: "Regional reporting",
                      description: "Controlled regional reporting products.",
                      isMember: false,
                      applicationStatus: null,
                      applicationId: null,
                      canReviewApplications: false,
                      canManageAdmins: false,
                      managerNames: ["ACG Manager"],
                    },
                  ],
                },
        ),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AccessGroupsPage />, "/access-groups", session);
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/acgs/catalogue?page=1&pageSize=50",
      { credentials: "include", method: "GET" },
    ),
  );
  await userEvent.type(
    await screen.findByLabelText(/Why do you need access/),
    "Required for my assigned regional assessment.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Submit application" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/acgs/acg-1/applications",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(await screen.findByText("Application submitted.")).toBeVisible();
});

test("lets users browse beyond the first catalogue page", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve(
            url.includes("/acg-applications")
              ? { applications: [], page: 1, pageSize: 20, total: 0, totalPages: 0 }
              : {
                  acgs: [
                    {
                      id: url.includes("page=2") ? "acg-21" : "acg-1",
                      code: url.includes("page=2") ? "ACG-21" : "ACG-01",
                      name: url.includes("page=2")
                        ? "Later catalogue group"
                        : "First catalogue group",
                      description: "Controlled products.",
                      isMember: false,
                      applicationStatus: null,
                      applicationId: null,
                      canReviewApplications: false,
                      canManageAdmins: false,
                    },
                  ],
                  page: url.includes("page=2") ? 2 : 1,
                  pageSize: 20,
                  total: 21,
                  totalPages: 2,
                },
          ),
      }),
    ),
  );

  renderWithProviders(<AccessGroupsPage />, "/access-groups", session);
  expect((await screen.findAllByText("First catalogue group"))[0]).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Next" }));
  expect((await screen.findAllByText("Later catalogue group"))[0]).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Previous" }));
  expect((await screen.findAllByText("First catalogue group"))[0]).toBeVisible();
});

test("shows a delegated review and retains decision feedback", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  let decided = false;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      let body: object;
      if (url.includes("/decision") && init?.method === "POST") {
        decided = true;
        body = { id: "application-1", status: "approved" };
      } else if (url.includes("/acg-applications")) {
        body = {
          applications: decided
            ? []
            : [
                {
                  id: "application-1",
                  acgId: "acg-1",
                  acgCode: "ACG-ONE",
                  acgName: "Regional reporting",
                  applicantUserId: "user-2",
                  applicantDisplayName: "Other User",
                  justification: "Assigned work requires access.",
                  status: "pending",
                  submittedAt: "2026-07-12T10:00:00Z",
                },
              ],
        };
      } else {
        body = {
          acgs: [
            {
              id: "acg-1",
              code: "ACG-ONE",
              name: "Regional reporting",
              description: "Controlled products.",
              isMember: false,
              applicationStatus: null,
              applicationId: null,
              canReviewApplications: true,
              canManageAdmins: false,
            },
          ],
          page: 1,
          pageSize: 20,
          total: 1,
          totalPages: 1,
        };
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    }),
  );

  renderWithProviders(<AccessGroupsPage />, "/access-groups", session);
  await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
  expect(await screen.findByText("Other User's application was approved.")).toBeVisible();
  expect(await screen.findByText("No applications await review.")).toBeVisible();
});

test("lets a platform administrator manage delegated administrators", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const adminSession: AuthSession = {
    ...session,
    user: {
      ...session.user,
      roles: ["Administrator"],
      permissions: ["user:read_self", "role:manage", "system:configure"],
    },
  };
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    let body: object = {};
    if (url.includes("/acg-applications")) {
      body = { applications: [], page: 1, pageSize: 20, total: 0, totalPages: 0 };
    } else if (url.includes("admin-directory")) {
      body = {
        users: [{ id: "candidate-1", username: "candidate@test", displayName: "Candidate One" }],
        page: 1,
        pageSize: 20,
        total: 1,
        totalPages: 1,
      };
    } else if (url.endsWith("/admins") && init?.method === "GET") {
      body = {
        admins: [
          { id: "admin-1", username: "admin@test", displayName: "Platform Admin" },
          { id: "admin-2", username: "second@test", displayName: "Second Admin" },
        ],
      };
    } else if (url.includes("/admins/")) {
      body = { admins: [] };
    } else {
      body = {
        acgs: [
          {
            id: "acg-1",
            code: "ACG-ONE",
            name: "Regional reporting",
            description: "Controlled products.",
            isMember: false,
            applicationStatus: null,
            applicationId: null,
            canReviewApplications: true,
            canManageAdmins: true,
          },
        ],
        page: 1,
        pageSize: 20,
        total: 1,
        totalPages: 1,
      };
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AccessGroupsPage />, "/access-groups", adminSession);
  expect(await screen.findByText("Platform Admin")).toBeVisible();
  await userEvent.type(screen.getByLabelText("Find an active user"), "Can");
  await userEvent.click(await screen.findByRole("button", { name: "Add Candidate One" }));
  expect(await screen.findByText("Group administrator added.")).toBeVisible();
  await userEvent.click(
    screen.getByRole("button", { name: "Remove Second Admin as group administrator" }),
  );
  expect(await screen.findByText("Group administrator removed.")).toBeVisible();
});

test("shows membership states and lets a user withdraw a pending application", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const statuses = [
    ["member", true, null],
    ["pending", false, "pending"],
    ["rejected", false, "rejected"],
    ["approved", false, "approved"],
    ["withdrawn", false, "withdrawn"],
  ] as const;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve(
            url.includes("/acg-applications")
              ? { applications: [], page: 1, pageSize: 20, total: 0, totalPages: 0 }
              : url.includes("/applications/mine")
                ? {}
                : {
                    acgs: statuses.map(([name, isMember, applicationStatus]) => ({
                      id: `acg-${name}`,
                      code: `ACG-${name}`,
                      name,
                      description: "Controlled products.",
                      isMember,
                      applicationStatus,
                      applicationId: applicationStatus ? `application-${name}` : null,
                      canReviewApplications: false,
                      canManageAdmins: false,
                    })),
                    page: 1,
                    pageSize: 20,
                    total: statuses.length,
                    totalPages: 1,
                  },
          ),
      }),
    ),
  );

  renderWithProviders(<AccessGroupsPage />, "/access-groups", session);
  expect((await screen.findAllByText("Member"))[0]).toBeVisible();
  expect(screen.getByText("Application rejected")).toBeVisible();
  expect(screen.getByText("Application approved")).toBeVisible();
  expect(screen.getByText("Application withdrawn")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /pending Application pending/i }));
  await userEvent.click(screen.getByRole("button", { name: "Withdraw application" }));
  expect(await screen.findByText("Application withdrawn.")).toBeVisible();
});

test("searches the active ACG catalogue and explains an empty result", async () => {
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve(
          url.includes("/acg-applications")
            ? { applications: [], page: 1, pageSize: 20, total: 0, totalPages: 0 }
            : url.includes("query=missing")
              ? { acgs: [], page: 1, pageSize: 50, total: 0, totalPages: 0 }
              : {
                  acgs: [
                    {
                      id: "acg-1",
                      code: "ACG-ONE",
                      name: "Regional reporting",
                      description: "Controlled products.",
                      isMember: false,
                      applicationStatus: null,
                      applicationId: null,
                      canReviewApplications: false,
                      canManageAdmins: false,
                      managerNames: ["Current Manager"],
                    },
                  ],
                  page: 1,
                  pageSize: 50,
                  total: 1,
                  totalPages: 1,
                },
        ),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AccessGroupsPage />, "/access-groups", session);
  expect(await screen.findByText("1 active access group matches this view.")).toBeVisible();
  await userEvent.type(await screen.findByLabelText("Search access groups"), "missing");

  expect(await screen.findByText("No ACGs match your search.")).toBeVisible();
  expect(screen.getByText("Choose a different search to view an access group.")).toBeVisible();
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/acgs/catalogue?page=1&pageSize=50&query=missing",
    expect.objectContaining({ method: "GET" }),
  );
});
