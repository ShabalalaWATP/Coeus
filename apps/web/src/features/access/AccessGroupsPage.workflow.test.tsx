import { screen, waitFor, within } from "@testing-library/react";
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

test("prevents self-decision and lets a delegated administrator reject another application", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  let decided = false;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      const group = {
        id: "acg-1",
        code: "ACG-ONE",
        name: "Regional reporting",
        description: "Controlled products.",
        isMember: false,
        applicationStatus: null,
        applicationId: null,
        canReviewApplications: true,
        canManageAdmins: false,
      };
      const applications = [
        { id: "self", applicantUserId: "user-1", applicantDisplayName: "Requesting User" },
        { id: "other", applicantUserId: "user-2", applicantDisplayName: "Other User" },
      ].map((item) => ({
        ...item,
        acgId: "acg-1",
        acgCode: "ACG-ONE",
        acgName: "Regional reporting",
        justification: "Assigned work requires access.",
        status: "pending",
        submittedAt: "2026-07-12T10:00:00Z",
      }));
      const body =
        url.includes("/decision") && init?.method === "POST"
          ? ((decided = true), { ...applications[1], status: "rejected" })
          : url.includes("/acg-applications")
            ? {
                applications: decided ? [] : applications,
                page: 1,
                pageSize: 20,
                total: 2,
                totalPages: 1,
              }
            : { acgs: [group], page: 1, pageSize: 20, total: 1, totalPages: 1 };
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    }),
  );

  renderWithProviders(<AccessGroupsPage />, "/access-groups", session);
  expect(await screen.findByText("You cannot decide your own application.")).toBeVisible();
  await userEvent.type(screen.getByLabelText("Rejection reason for Other User"), "Need not shown.");
  await userEvent.click(screen.getAllByRole("button", { name: "Reject" })[1]);
  expect(await screen.findByText("Other User's application was rejected.")).toBeVisible();
});

test("pages through a delegated review queue in both directions", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const page = Number(new URL(url).searchParams.get("page") ?? "1");
      const body = url.includes("/acg-applications")
        ? {
            applications: [
              {
                id: `application-${page}`,
                acgId: "acg-1",
                acgName: "Regional reporting",
                applicantUserId: `user-${page + 1}`,
                applicantDisplayName: `Applicant ${page}`,
                justification: "Assigned work requires access.",
                status: "pending",
                submittedAt: "2026-07-12T10:00:00Z",
              },
            ],
            page,
            pageSize: 20,
            total: 21,
            totalPages: 2,
          }
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
                canReviewApplications: true,
                canManageAdmins: false,
              },
            ],
            page: 1,
            pageSize: 20,
            total: 1,
            totalPages: 1,
          };
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    }),
  );

  renderWithProviders(<AccessGroupsPage />, "/access-groups", session);
  expect(await screen.findByText("Applicant 1")).toBeVisible();
  const reviewPages = screen.getByRole("navigation", { name: "Application review pages" });
  await userEvent.click(within(reviewPages).getByRole("button", { name: "Next" }));
  expect(await screen.findByText("Applicant 2")).toBeVisible();
  await userEvent.click(
    within(screen.getByRole("navigation", { name: "Application review pages" })).getByRole(
      "button",
      { name: "Previous" },
    ),
  );
  expect(await screen.findByText("Applicant 1")).toBeVisible();
});

test("shows retry controls when catalogue and delegated review loading fail", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable." } }),
    }),
  );

  renderWithProviders(<AccessGroupsPage />, "/access-groups", session);
  await waitFor(() => expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(2), {
    timeout: 12_000,
  });
  const retries = screen.getAllByRole("button", { name: "Retry" });
  expect(retries).toHaveLength(2);
  await userEvent.click(retries[0]);
  await userEvent.click(retries[1]);
});

test("keeps application controls usable when apply and withdrawal requests fail", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST" || init?.method === "DELETE") {
        return Promise.resolve({
          ok: false,
          status: 409,
          json: () =>
            Promise.resolve({ error: { code: "stale", message: "The request is stale." } }),
        });
      }
      const body = url.includes("/acg-applications")
        ? { applications: [], page: 1, pageSize: 20, total: 0, totalPages: 0 }
        : {
            acgs: [
              {
                id: "acg-apply",
                code: "ACG-APPLY",
                name: "Apply group",
                description: "Controlled products.",
                isMember: false,
                applicationStatus: null,
                applicationId: null,
                canReviewApplications: false,
                canManageAdmins: false,
              },
              {
                id: "acg-pending",
                code: "ACG-PENDING",
                name: "Pending group",
                description: "Controlled products.",
                isMember: false,
                applicationStatus: "pending",
                applicationId: "application-pending",
                canReviewApplications: false,
                canManageAdmins: false,
              },
            ],
            page: 1,
            pageSize: 20,
            total: 2,
            totalPages: 1,
          };
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
    }),
  );

  renderWithProviders(<AccessGroupsPage />, "/access-groups", session);
  await userEvent.click(await screen.findByRole("button", { name: /Apply group/ }));
  await userEvent.type(
    await screen.findByLabelText(/Why do you need access/),
    "Required for assigned assessment work.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Submit application" }));
  expect(await screen.findByText("The request is stale.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /Pending group/ }));
  await userEvent.click(screen.getByRole("button", { name: "Withdraw application" }));
  expect(await screen.findByText("The request is stale.")).toBeVisible();
});
